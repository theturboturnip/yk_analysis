import argparse
from typing import cast
from analysis_helpers.data import ShaderAggregate
from analysis_helpers.vertex import GMDVertexBufferLayout

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    args = parser.parse_args()

    with open(args.report, "r") as f:
        shader_analysis = [
            eval(l)
            for l in f.readlines()
            if l.strip()
        ]

    shader_analysis.sort(key=lambda s: s.shader[2:])

    columns = [
        "NVertPos",
        "NVertWeight",
        "NVertBones",
        "NVertNormal",
        "NVertTangent",
        "NVertUnk",
        "NVertCol0",
        "NVertCol1",
    ] + [
        f"NUV{i}" for i in range(8)
    ] + [
        "(Un)skinned",
        "TexDiffuse",
        "TexRefl",
        "TexMulti",
        "TexRm",
        "TexTs",
        "TexNormal",
        "TexRt",
        "TexRd",
    ] + [
        f"Mat-{k}" for k in shader_analysis[0].material.keys()
    ] + [
        f"Ext{i:02d}" for i in range(16)
    ]


    print(f"{'Name': <30}\t", "\t".join(columns))
    for s in shader_analysis:
        s = cast(ShaderAggregate, s)

        print(f"{s.shader: <30}", end="\t")

        # vertex flags
        (vflags, vbytes) = next(iter(s.vertex_format))
        layout = GMDVertexBufferLayout.build_vertex_buffer_layout_from_flags(vflags)
        storage_ns = [
            layout.pos_storage.n_comps,
            layout.weights_storage.n_comps if layout.weights_storage else 0,
            layout.bones_storage.n_comps if layout.bones_storage else 0,
            layout.normal_storage.n_comps if layout.normal_storage else 0,
            layout.tangent_storage.n_comps if layout.tangent_storage else 0,
            layout.unk_storage.n_comps if layout.unk_storage else 0,
            layout.col0_storage.n_comps if layout.col0_storage else 0,
            layout.col1_storage.n_comps if layout.col1_storage else 0,
        ] + [
            layout.uv_storages[i].n_comps if i < len(layout.uv_storages) else 0
            for i in range(8)
        ]
        # pos_storage: VecStorage
        # weights_storage: Optional[VecStorage]
        # bones_storage: Optional[VecStorage]
        # normal_storage: Optional[VecStorage]
        # tangent_storage: Optional[VecStorage]
        # unk_storage: Optional[VecStorage]
        # col0_storage: Optional[VecStorage]
        # col1_storage: Optional[VecStorage]
        # uv_storages: Tuple[VecStorage, ...] # max length 8
        print("\t".join(str(x) for x in storage_ns), end="\t")

        # skinning
        if s.uses_matrices == {False}:
            skin = "Unskin"
        elif s.uses_matrices == {True}:
            skin = "Skin"
        elif s.uses_matrices == {True, False}:
            skin = "Both"
        else:
            skin = f"unk{s.uses_matrices}"
        print(skin, end="\t")
        
        for t in s.textures:
            print(t, end="\t")
        for v in s.material.values():
            print(v, end="\t")
        for e in s.extra_properties:
            print(e, end="\t")
        print()