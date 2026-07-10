#!/usr/bin/env python3
"""Generate cube_a.stl and cube_b.stl — two 10 mm ASCII-STL cubes used as the
pyslic3r M0 fixtures. Loaded as two separate model objects (expected
object_count == 2). Regenerate with: python3 gen_two_object_stls.py [outdir]
"""
import os
import sys

V = [(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0),
     (0, 0, 10), (10, 0, 10), (10, 10, 10), (0, 10, 10)]
T = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
     (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]


def write_cube(path: str, name: str, dx: float) -> None:
    with open(path, "w") as f:
        f.write(f"solid {name}\n")
        for a, b, c in T:
            f.write(" facet normal 0 0 0\n  outer loop\n")
            for i in (a, b, c):
                x, y, z = V[i]
                f.write(f"   vertex {x + dx:.1f} {y:.1f} {z:.1f}\n")
            f.write("  endloop\n endfacet\n")
        f.write(f"endsolid {name}\n")


def main() -> None:
    outdir = sys.argv[1] if len(sys.argv) > 1 else "."
    write_cube(os.path.join(outdir, "cube_a.stl"), "cube_a", 0.0)
    write_cube(os.path.join(outdir, "cube_b.stl"), "cube_b", 30.0)
    print(f"wrote cube_a.stl, cube_b.stl to {outdir}")


if __name__ == "__main__":
    main()
