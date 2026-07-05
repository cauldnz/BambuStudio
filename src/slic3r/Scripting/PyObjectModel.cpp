// pyslic3r read-only object model (M1).
//
// Exposes Application / Document / Model tree / Config / Plates as an
// inspection-only surface. Invariants:
//   - Read-only: every member is a getter; nothing here mutates the document,
//     config, or presets.
//   - UI-parity: everything routes through Plater and the objects it owns
//     (Model, PartPlateList, DynamicPrintConfig, PresetBundle) — never a
//     parallel data path.
//   - Main-thread-guarded: every accessor asserts the wx main thread, so
//     off-thread callers must come through run_on_main_blocking().
//   - Handles are indices, re-resolved per call and bounds-checked, so a stale
//     Python handle raises rather than dereferencing a freed pointer if the
//     model changed between calls.

#include "PyBindings.hpp"

#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#include <pybind11/stl.h>

#include <wx/app.h>
#include <wx/thread.h>

#include "libslic3r/libslic3r.h"
#include "libslic3r/Model.hpp"
#include "libslic3r/BoundingBox.hpp"
#include "libslic3r/Config.hpp"
#include "libslic3r/Preset.hpp"
#include "libslic3r/PresetBundle.hpp"
#include "slic3r/GUI/GUI_App.hpp"
#include "slic3r/GUI/Plater.hpp"
#include "slic3r/GUI/PartPlate.hpp"

namespace py = pybind11;
using namespace Slic3r;

namespace pyslic3r {
namespace {

// ---- guards + resolvers ---------------------------------------------------

void main_thread(const char *what)
{
    if (!wxThread::IsMain())
        throw std::runtime_error(std::string(what) +
            " must be accessed on the wx main thread; use the marshalling primitive");
}

GUI::Plater *plater_or_throw(const char *what)
{
    main_thread(what);
    auto *p = GUI::wxGetApp().plater();
    if (p == nullptr)
        throw std::runtime_error("no active document");
    return p;
}

Model &model_or_throw(const char *what) { return plater_or_throw(what)->model(); }

ModelObject *object_at(size_t idx, const char *what)
{
    Model &m = model_or_throw(what);
    if (idx >= m.objects.size())
        throw std::runtime_error("object index out of range (model changed?)");
    return m.objects[idx];
}

// ---- small value converters ----------------------------------------------

py::tuple vec3(const Vec3d &v) { return py::make_tuple(v.x(), v.y(), v.z()); }

const char *volume_type_str(ModelVolumeType t)
{
    switch (t) {
    case ModelVolumeType::MODEL_PART:         return "model_part";
    case ModelVolumeType::NEGATIVE_VOLUME:    return "negative_volume";
    case ModelVolumeType::PARAMETER_MODIFIER: return "modifier";
    case ModelVolumeType::SUPPORT_BLOCKER:    return "support_blocker";
    case ModelVolumeType::SUPPORT_ENFORCER:   return "support_enforcer";
    default:                                  return "invalid";
    }
}

// ---- handle types ---------------------------------------------------------
// Each holds indices only; the referenced C++ object is re-resolved per call.

struct PyApp {};
struct PyDocument {};
struct PyModel {};
struct PyObject   { size_t idx; };
struct PyVolume   { size_t obj_idx; size_t vol_idx; };
struct PyPlateList {};
struct PyPlate    { int idx; };

// Which config a PyConfig fronts.
enum class ConfigSource { Global, Print, Filament, Printer, Plate };
struct PyConfig { ConfigSource source; int plate_idx = 0; };

const ConfigBase *resolve_config(const PyConfig &c, const char *what)
{
    auto &app = GUI::wxGetApp();
    switch (c.source) {
    case ConfigSource::Global: {
        const DynamicPrintConfig *cfg = plater_or_throw(what)->config();
        if (cfg == nullptr) throw std::runtime_error("no global config");
        return cfg;
    }
    case ConfigSource::Print:
        main_thread(what);
        return &app.preset_bundle->prints.get_selected_preset().config;
    case ConfigSource::Filament:
        main_thread(what);
        return &app.preset_bundle->filaments.get_selected_preset().config;
    case ConfigSource::Printer:
        main_thread(what);
        return &app.preset_bundle->printers.get_selected_preset().config;
    case ConfigSource::Plate: {
        auto &list = plater_or_throw(what)->get_partplate_list();
        if (c.plate_idx < 0 || c.plate_idx >= list.get_plate_count())
            throw std::runtime_error("plate index out of range");
        GUI::PartPlate *plate = list.get_plate(c.plate_idx);
        if (plate == nullptr || plate->config() == nullptr)
            throw std::runtime_error("no plate config");
        return plate->config();
    }
    }
    throw std::runtime_error("unknown config source");
}

ModelVolume *volume_at(const PyVolume &v, const char *what)
{
    ModelObject *obj = object_at(v.obj_idx, what);
    if (v.vol_idx >= obj->volumes.size())
        throw std::runtime_error("volume index out of range (model changed?)");
    return obj->volumes[v.vol_idx];
}

} // anonymous namespace

// ---------------------------------------------------------------------------

void register_object_model(py::module_ &m)
{
    // ---- Config -----------------------------------------------------------
    py::class_<PyConfig>(m, "Config")
        .def("has", [](const PyConfig &c, const std::string &key) {
            return resolve_config(c, "Config.has")->has(key);
        })
        .def("get", [](const PyConfig &c, const std::string &key) -> py::object {
            const ConfigBase *cfg = resolve_config(c, "Config.get");
            if (!cfg->has(key))
                return py::none();
            return py::str(cfg->opt_serialize(key));   // serialized string form
        })
        .def("keys", [](const PyConfig &c) {
            return resolve_config(c, "Config.keys")->keys();   // -> list[str]
        });

    // ---- Volume -----------------------------------------------------------
    py::class_<PyVolume>(m, "Volume")
        .def_property_readonly("name", [](const PyVolume &v) {
            return volume_at(v, "Volume.name")->name;
        })
        .def_property_readonly("type", [](const PyVolume &v) {
            return std::string(volume_type_str(volume_at(v, "Volume.type")->type()));
        })
        .def_property_readonly("is_model_part", [](const PyVolume &v) {
            return volume_at(v, "Volume.is_model_part")->is_model_part();
        });

    // ---- Object -----------------------------------------------------------
    py::class_<PyObject>(m, "Object")
        .def_property_readonly("name", [](const PyObject &o) {
            return object_at(o.idx, "Object.name")->name;
        })
        .def_property_readonly("instance_count", [](const PyObject &o) {
            return object_at(o.idx, "Object.instance_count")->instances.size();
        })
        .def_property_readonly("volumes", [](const PyObject &o) {
            ModelObject *obj = object_at(o.idx, "Object.volumes");
            py::list out;
            for (size_t i = 0; i < obj->volumes.size(); ++i)
                out.append(PyVolume{o.idx, i});
            return out;
        })
        .def("bounding_box", [](const PyObject &o) {
            const BoundingBoxf3 &bb = object_at(o.idx, "Object.bounding_box")->bounding_box();
            py::dict d;
            d["min"]    = vec3(bb.min);
            d["max"]    = vec3(bb.max);
            d["size"]   = vec3(bb.size());
            d["center"] = vec3(bb.center());
            return d;
        });

    // ---- Model ------------------------------------------------------------
    py::class_<PyModel>(m, "Model")
        .def_property_readonly("object_count", [](const PyModel &) {
            return model_or_throw("Model.object_count").objects.size();
        })
        .def_property_readonly("objects", [](const PyModel &) {
            Model &mo = model_or_throw("Model.objects");
            py::list out;
            for (size_t i = 0; i < mo.objects.size(); ++i)
                out.append(PyObject{i});
            return out;
        });

    // ---- Plate / PlateList ------------------------------------------------
    py::class_<PyPlate>(m, "Plate")
        .def_property_readonly("index", [](const PyPlate &p) { return p.idx; })
        .def_property_readonly("object_count", [](const PyPlate &p) {
            auto &list = plater_or_throw("Plate.object_count")->get_partplate_list();
            GUI::PartPlate *plate = list.get_plate(p.idx);
            if (plate == nullptr) throw std::runtime_error("plate gone");
            return plate->get_objects_on_this_plate().size();
        })
        .def_property_readonly("is_sliceable", [](const PyPlate &p) {
            auto &list = plater_or_throw("Plate.is_sliceable")->get_partplate_list();
            GUI::PartPlate *plate = list.get_plate(p.idx);
            if (plate == nullptr) throw std::runtime_error("plate gone");
            return plate->can_slice();
        })
        .def_property_readonly("config", [](const PyPlate &p) {
            return PyConfig{ConfigSource::Plate, p.idx};
        });

    py::class_<PyPlateList>(m, "PlateList")
        .def_property_readonly("count", [](const PyPlateList &) {
            return plater_or_throw("PlateList.count")->get_partplate_list().get_plate_count();
        })
        .def("__len__", [](const PyPlateList &) {
            return plater_or_throw("PlateList.__len__")->get_partplate_list().get_plate_count();
        })
        .def("__getitem__", [](const PyPlateList &, int i) {
            int n = plater_or_throw("PlateList[]")->get_partplate_list().get_plate_count();
            if (i < 0 || i >= n) throw py::index_error("plate index out of range");
            return PyPlate{i};
        });

    // ---- Document ---------------------------------------------------------
    py::class_<PyDocument>(m, "Document")
        // Kept from M0 for continuity:
        .def_property_readonly("object_count", [](const PyDocument &) {
            return model_or_throw("Document.object_count").objects.size();
        })
        .def_property_readonly("model", [](const PyDocument &) { return PyModel{}; })
        .def_property_readonly("plates", [](const PyDocument &) { return PyPlateList{}; })
        .def_property_readonly("config", [](const PyDocument &) {
            return PyConfig{ConfigSource::Global};
        })
        .def_property_readonly("print_config", [](const PyDocument &) {
            return PyConfig{ConfigSource::Print};
        })
        .def_property_readonly("filament_config", [](const PyDocument &) {
            return PyConfig{ConfigSource::Filament};
        })
        .def_property_readonly("printer_config", [](const PyDocument &) {
            return PyConfig{ConfigSource::Printer};
        });

    // ---- Application ------------------------------------------------------
    py::class_<PyApp>(m, "Application")
        .def_property_readonly("version", [](const PyApp &) {
            main_thread("app.version");
            return std::string(SLIC3R_VERSION);
        })
        .def_property_readonly("active_document", [](const PyApp &) -> py::object {
            main_thread("app.active_document");
            if (GUI::wxGetApp().plater() == nullptr)
                return py::none();
            return py::cast(PyDocument{});
        })
        .def_property_readonly("selected_printer", [](const PyApp &) {
            main_thread("app.selected_printer");
            return GUI::wxGetApp().preset_bundle->printers.get_selected_preset_name();
        })
        .def("printers", [](const PyApp &) {
            main_thread("app.printers");
            // Mirror the GUI dropdown: visible printer presets only.
            std::vector<std::string> out;
            for (const Preset &p : GUI::wxGetApp().preset_bundle->printers.get_presets())
                if (p.is_visible)
                    out.push_back(p.name);
            return out;
        });

    m.attr("app") = py::cast(PyApp{});
}

} // namespace pyslic3r
