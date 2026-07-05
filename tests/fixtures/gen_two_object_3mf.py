#!/usr/bin/env python3
"""Generate two_object.3mf — a minimal, standard-conformant 3MF containing two
10 mm cube mesh objects, used by the pyslic3r M0 self-test (expected
object_count == 2). Deterministic output; regenerate with:
    python3 gen_two_object_3mf.py [out.3mf]
"""
import sys
import zipfile

CUBE_VERTICES = [
    (0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0),
    (0, 0, 10), (10, 0, 10), (10, 10, 10), (0, 10, 10),
]
# Outward-facing (CCW seen from outside).
CUBE_TRIANGLES = [
    (0, 2, 1), (0, 3, 2),   # bottom
    (4, 5, 6), (4, 6, 7),   # top
    (0, 1, 5), (0, 5, 4),   # front
    (1, 2, 6), (1, 6, 5),   # right
    (2, 3, 7), (2, 7, 6),   # back
    (3, 0, 4), (3, 4, 7),   # left
]


def mesh_xml() -> str:
    verts = "\n".join(
        f'      <vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in CUBE_VERTICES)
    tris = "\n".join(
        f'      <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in CUBE_TRIANGLES)
    return f"    <mesh>\n     <vertices>\n{verts}\n     </vertices>\n" \
           f"     <triangles>\n{tris}\n     </triangles>\n    </mesh>"


MODEL = f"""<?xml version="1.0" encoding="UTF-8"?>
<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
 <resources>
  <object id="1" type="model">
{mesh_xml()}
  </object>
  <object id="2" type="model">
{mesh_xml()}
  </object>
 </resources>
 <build>
  <item objectid="1" transform="1 0 0 0 1 0 0 0 1 100 100 0"/>
  <item objectid="2" transform="1 0 0 0 1 0 0 0 1 130 100 0"/>
 </build>
</model>
"""

CONTENT_TYPES = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
 <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
 <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>
</Types>
"""

RELS = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>
</Relationships>
"""


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "two_object.3mf"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        # Fixed date_time keeps the artifact byte-stable across regenerations.
        for name, data in (
            ("[Content_Types].xml", CONTENT_TYPES),
            ("_rels/.rels", RELS),
            ("3D/3dmodel.model", MODEL),
        ):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, data)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
