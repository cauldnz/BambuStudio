// pyslic3r cloud device plane (M4) — READ-ONLY surface.
//
// Login state, account-bound printer enumeration, selection, and status
// read-back, routed through the same NetworkAgent / DeviceManager the GUI's
// Device page uses. Invariants:
//   - Read-only here: no send/print/config — those are gated behind explicit
//     user intent and a later slice (M4 write half).
//   - Strictly isolated: everything degrades gracefully if the network plugin
//     isn't loaded or the cloud is unreachable (null checks, never throw the
//     whole app down). A cloud outage must not affect model/slice work.
//   - Main-thread-guarded: NetworkAgent/DeviceManager live on the wx main
//     thread; off-thread callers must come through run_on_main_blocking.
//   - Handles are dev_id strings, re-resolved per call — a stale handle
//     returns None/raises rather than dereferencing a freed MachineObject.

#include "PyBindings.hpp"

#include <chrono>
#include <map>
#include <string>

#include <pybind11/stl.h>

#include <wx/app.h>
#include <wx/thread.h>
#include <wx/utils.h>   // wxMilliSleep

#include "slic3r/GUI/GUI_App.hpp"
#include "slic3r/Utils/NetworkAgent.hpp"
#include "slic3r/GUI/DeviceCore/DevManager.h"
#include "slic3r/GUI/DeviceManager.hpp"

namespace py = pybind11;
using namespace Slic3r;

namespace pyslic3r {
namespace {

void dev_main_thread(const char *what)
{
    if (!wxThread::IsMain())
        throw std::runtime_error(std::string(what) +
            " must be accessed on the wx main thread; use the marshalling primitive");
}

// NetworkAgent is null until the signed network plugin is loaded. Return it
// (possibly null) — callers treat null as "device plane unavailable".
NetworkAgent *agent(const char *what)
{
    dev_main_thread(what);
    return GUI::wxGetApp().getAgent();
}

DeviceManager *devmgr(const char *what)
{
    dev_main_thread(what);
    return GUI::wxGetApp().getDeviceManager();
}

bool logged_in(const char *what)
{
    NetworkAgent *a = agent(what);
    return a != nullptr && a->is_user_login();
}

// dev_id -> MachineObject*, or nullptr if gone.
MachineObject *machine(const std::string &dev_id, const char *what)
{
    DeviceManager *dm = devmgr(what);
    return dm == nullptr ? nullptr : dm->get_my_machine(dev_id);
}

// Merged account-bound + local machine list (dev_id -> MachineObject*).
std::map<std::string, MachineObject *> all_machines(const char *what)
{
    DeviceManager *dm = devmgr(what);
    std::map<std::string, MachineObject *> out;
    if (dm == nullptr) return out;
    out = dm->get_my_machine_list();                       // local + mine
    for (auto &kv : dm->get_user_machinelist())            // account-bound (cloud)
        if (kv.second != nullptr) out.emplace(kv.first, kv.second);
    return out;
}

struct PyDevice {};
struct PyBoundPrinter { std::string dev_id; };

} // anonymous namespace

void register_device(py::module_ &m)
{
    // ---- BoundPrinter -----------------------------------------------------
    py::class_<PyBoundPrinter>(m, "BoundPrinter")
        .def_property_readonly("dev_id", [](const PyBoundPrinter &p) { return p.dev_id; })
        .def_property_readonly("name", [](const PyBoundPrinter &p) {
            MachineObject *mo = machine(p.dev_id, "BoundPrinter.name");
            return mo ? mo->get_dev_name() : std::string();
        })
        .def_property_readonly("online", [](const PyBoundPrinter &p) {
            MachineObject *mo = machine(p.dev_id, "BoundPrinter.online");
            return mo ? mo->is_online() : false;
        })
        .def_property_readonly("connection_type", [](const PyBoundPrinter &p) {
            MachineObject *mo = machine(p.dev_id, "BoundPrinter.connection_type");
            return mo ? mo->connection_type() : std::string();
        });

    // ---- Device -----------------------------------------------------------
    py::class_<PyDevice>(m, "Device")
        // Is the signed network plugin loaded at all?
        .def_property_readonly("available", [](const PyDevice &) {
            return agent("Device.available") != nullptr;
        })
        .def_property_readonly("is_logged_in", [](const PyDevice &) {
            return logged_in("Device.is_logged_in");
        })
        .def_property_readonly("user_id", [](const PyDevice &) -> py::object {
            NetworkAgent *a = agent("Device.user_id");
            if (a == nullptr || !a->is_user_login()) return py::none();
            return py::str(a->get_user_id());
        })
        .def_property_readonly("user_name", [](const PyDevice &) -> py::object {
            NetworkAgent *a = agent("Device.user_name");
            if (a == nullptr || !a->is_user_login()) return py::none();
            std::string n = a->get_user_nickanme();          // (sic — upstream typo)
            if (n.empty()) n = a->get_user_name();
            return py::str(n);
        })
        .def("printers", [](const PyDevice &) {
            // Account-bound (+ local) printers, from the cached list. Call
            // refresh() first to fetch it from the cloud (a fresh instance
            // hasn't). Empty list is a valid result (nothing bound).
            py::list out;
            for (auto &kv : all_machines("Device.printers"))
                out.append(PyBoundPrinter{kv.first});
            return out;
        })
        .def("refresh", [](const PyDevice &) {
            // Fetch the account's bound-printer list from the cloud (what the
            // GUI does on the Device page). update_user_machine_list_info()
            // makes a synchronous HTTP call then defers the JSON parse via
            // CallAfter — so pump the event loop until the list populates,
            // then return the count. Returns 0 if not logged in / unavailable.
            DeviceManager *dm = devmgr("Device.refresh");
            if (dm == nullptr) return size_t(0);
            NetworkAgent *a = GUI::wxGetApp().getAgent();
            if (a == nullptr || !a->is_user_login()) return size_t(0);

            dm->update_user_machine_list_info();
            {
                py::gil_scoped_release nogil;
                using clock = std::chrono::steady_clock;
                const auto t0 = clock::now();
                for (;;) {
                    if (wxTheApp != nullptr) wxTheApp->Yield(true);   // run the parse
                    if (!dm->get_user_machinelist().empty()) break;  // populated
                    if (clock::now() - t0 > std::chrono::seconds(8)) break;
                    wxMilliSleep(80);
                }
            }
            return dm->get_user_machinelist().size();
        })
        .def_property_readonly("selected", [](const PyDevice &) -> py::object {
            DeviceManager *dm = devmgr("Device.selected");
            if (dm == nullptr) return py::none();
            MachineObject *mo = dm->get_selected_machine();
            if (mo == nullptr) return py::none();
            return py::cast(PyBoundPrinter{mo->get_dev_id()});
        })
        .def("select", [](const PyDevice &, const std::string &dev_id) {
            DeviceManager *dm = devmgr("Device.select");
            if (dm == nullptr || !dm->set_selected_machine(dev_id))
                throw std::runtime_error("could not select device: " + dev_id);
        }, py::arg("dev_id"))
        .def("status", [](const PyDevice &) -> py::object {
            // Status for the selected printer. None if nothing selected /
            // unavailable. Direct MachineObject fields (temps/HMS come with the
            // write half once a printer is bound to test against).
            DeviceManager *dm = devmgr("Device.status");
            if (dm == nullptr) return py::none();
            MachineObject *mo = dm->get_selected_machine();
            if (mo == nullptr) return py::none();
            py::dict d;
            d["dev_id"]         = mo->get_dev_id();
            d["online"]         = mo->is_online();
            d["print_status"]   = mo->print_status;          // RUNNING/PAUSE/FINISH/...
            d["progress"]       = mo->mc_print_percent;      // 0..100
            d["current_layer"]  = mo->curr_layer;
            d["total_layers"]   = mo->total_layers;
            d["remaining_s"]    = mo->mc_left_time;
            return d;
        });

    m.attr("_device_singleton") = py::cast(PyDevice{});
}

} // namespace pyslic3r
