import json
import sqlite3
import argparse
from dataclasses import dataclass
from typing import Any, Dict, Generator, List, Set, Tuple
from analysis_helpers.db import ReadOnlyDb
from analysis_helpers.data import ShaderAggregate

EXPECTED_DRAWCALL_DB_VERSION = 1

def cursor_iter(cursor, num_of_rows=100) -> Generator[Tuple, None, None]:
    while True:
        rows = cursor.fetchmany(num_of_rows)
        if not rows: break
        for row in rows:
            yield row

def analyze_shader(shader: str, gmd_db: ReadOnlyDb) -> ShaderAggregate:
    # Find all unique AttribSet.Flags associated with this shader
    gmd_db.cur.execute("SELECT DISTINCT Flags FROM AttribSet WHERE Shader = ?", (shader,))
    flags = {
        int.from_bytes(x)
        for (x,) in cursor_iter(gmd_db.cur)
    }
    # Find which texture slots are used with this shader
    gmd_db.cur.execute("SELECT TexDiffuse, TexRefl, TexMulti, TexRm, TexTs, TexNormal, TexRt, TexRd FROM AttribSet WHERE Shader = ?", (shader,))
    textures = [False] * 8
    for attribset_textures in cursor_iter(gmd_db.cur):
        for i in range(len(attribset_textures)):
            if attribset_textures[i] is not None:
                textures[i] = True
    # Find which parts of the material are used with this shader
    gmd_db.cur.execute("SELECT Material, ExtraProperties FROM AttribSet WHERE Shader = ?", (shader,))
    material = {}
    extra_properties = [False] * 16
    for (attribset_material, attribset_extras) in cursor_iter(gmd_db.cur):
        for (k, v) in json.loads(attribset_material).items():
            is_truthy = bool(v)
            if hasattr(v, "__iter__"):
                is_truthy = any(v)
            material[k] = is_truthy
        decoded_extras = json.loads(attribset_extras)
        for i in range(16):
            if decoded_extras[i]:
                extra_properties[i] = True
    # Find which vertex layout flags, bytespervert, and matrices are used with this shader
    gmd_db.cur.execute("SELECT DISTINCT VertLayoutFlags, BytesPerVert, MatrixCount FROM DrawCalls INNER JOIN AttribSet ON DrawCalls.AttribSetId = AttribSet.ROWID WHERE AttribSet.Shader = ?", (shader,))
    vertex_format = set()
    uses_matrices = set()
    for (draw_vlf, draw_bpv, draw_matrices) in cursor_iter(gmd_db.cur):
        vertex_format.add((
            int.from_bytes(draw_vlf),
            draw_bpv
        ))
        uses_matrices.add(draw_matrices > 0)

    return ShaderAggregate(
        shader=shader,
        flags=flags,
        textures=textures,
        material=material,
        extra_properties=extra_properties,
        vertex_format=vertex_format,
        uses_matrices=uses_matrices
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("db")
    parser.add_argument("report_file")
    args = parser.parse_args()

    db = ReadOnlyDb(args.db, expected_version=1)
    db.cur.execute("SELECT DISTINCT Shader FROM AttribSet")
    shaders = set(n for (n,) in cursor_iter(db.cur))

    # Look for notable points
    shaders_always_use_same_attribset_flags = True
    shaders_always_use_same_vertexlayout = True
    shaders_are_either_skinned_or_unskinned = True

    with open(args.report_file, "w") as report_file:
        for shader_name in shaders:
            shader = analyze_shader(shader_name, db)
            if shaders_always_use_same_attribset_flags and len(shader.flags) > 1:
                print(f"Shader {shader.shader} uses multiple attribset flags: ")
                for flag in shader.flags:
                    print(f"\t0x{flag:08x}")
                shaders_always_use_same_attribset_flags = False
            if shaders_always_use_same_vertexlayout and len(shader.vertex_format) > 1:
                print(f"Shader {shader.shader} uses multiple vertex layouts")
                for (vertex_layout_flags, bytes_per_vertex) in shader.vertex_format:
                    print(f"\t0x{vertex_layout_flags:08x}\t{bytes_per_vertex:d} bytes")
                shaders_always_use_same_vertexlayout = False
            if shaders_are_either_skinned_or_unskinned and len(shader.uses_matrices) > 1:
                print(f"Shader {shader.shader} works with both skinned and unskinned")
                shaders_are_either_skinned_or_unskinned = False
        
            print(f"{shader}", file=report_file)
    