#include "PyHost.hpp"
#include "PyBindings.hpp"

#include <chrono>
#include <future>
#include <memory>
#include <stdexcept>

#include <pybind11/embed.h>

#include <wx/app.h>
#include <wx/thread.h>

#include "libslic3r/libslic3r.h"
#include "libslic3r/Model.hpp"
#include "slic3r/GUI/GUI_App.hpp"
#include "slic3r/GUI/Plater.hpp"

namespace py = pybind11;

namespace pyslic3r {

namespace {

bool   s_initialized = false;
double s_init_ms     = 0.0;

// While the app is idle the main thread does not hold the GIL; it is parked
// here released so worker-marshalled Python (which always executes on the
// main thread) can acquire it around each call.
std::unique_ptr<py::gil_scoped_release> s_parked_gil;

void ensure_main_thread(const char *what)
{
    if (!wxThread::IsMain())
        throw std::runtime_error(std::string(what) +
            " must be accessed on the wx main thread; use the marshalling primitive");
}

} // anonymous namespace

// ---------------------------------------------------------------------------
// Embedded module. Thin composition point: the read-only object-model surface
// lives in PyObjectModel.cpp and is attached via register_object_model(). This
// TU is referenced by GUI_App, so the static module initializer can't be
// dropped by the linker.
// ---------------------------------------------------------------------------

PYBIND11_EMBEDDED_MODULE(pyslic3r, m)
{
    m.doc() = "pyslic3r — read-only embedded object model over the running app";
    register_object_model(m);
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

bool host_initialized() { return s_initialized; }
double interpreter_init_ms() { return s_init_ms; }

void host_init()
{
    ensure_main_thread("pyslic3r::host_init");
    if (s_initialized)
        return;

    const auto t0 = std::chrono::steady_clock::now();
    py::initialize_interpreter();
    {
        // Import once so the module's own init cost lands in s_init_ms and
        // later importers hit sys.modules.
        py::module_::import("pyslic3r");
    }
    const auto t1 = std::chrono::steady_clock::now();
    s_init_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

    // Park the GIL released; every Python call from here on acquires it
    // explicitly for the duration of the call only.
    s_parked_gil = std::make_unique<py::gil_scoped_release>();
    s_initialized = true;

    maybe_start_m0_selftest();
}

void host_shutdown()
{
    if (!s_initialized)
        return;
    ensure_main_thread("pyslic3r::host_shutdown");

    s_parked_gil.reset();       // reacquire the GIL for finalization
    py::finalize_interpreter();
    s_initialized = false;
}

// ---------------------------------------------------------------------------
// Marshalling primitive
// ---------------------------------------------------------------------------

void run_on_main_blocking(std::function<void()> fn)
{
    if (wxThread::IsMain()) {
        fn();
        return;
    }

    auto task = std::make_shared<std::packaged_task<void()>>(std::move(fn));
    std::future<void> done = task->get_future();

    // wxEvtHandler::CallAfter is documented thread-safe: it queues an event
    // to the main loop. The calling thread then blocks on the future — it
    // holds neither the GIL nor any wx object while waiting, so the main
    // thread is free to run the closure.
    wxTheApp->CallAfter([task]() { (*task)(); });

    done.get();     // rethrows any exception from fn on the calling thread
}

std::string py_eval_str(const std::string &expr)
{
    std::string out;
    run_on_main_blocking([&]() {
        py::gil_scoped_acquire gil;     // GIL held only around the Python call
        py::object ns  = py::module_::import("__main__").attr("__dict__");
        py::object res = py::eval(expr, ns);
        out = py::str(res).cast<std::string>();
    });
    return out;
}

} // namespace pyslic3r
