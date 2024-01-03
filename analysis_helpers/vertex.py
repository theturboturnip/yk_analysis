

from dataclasses import dataclass
from enum import Enum
import sys
from typing import Iterable, Optional, Set, Tuple


class VecCompFmt(Enum):
    Byte_0_1 = 0  # Fixed-point byte representation scaled between 0 and 1
    Byte_Minus1_1 = 1  # Fixed-point byte representation scaled between -1 and 1
    Byte_0_255 = 2  # Raw byte value, 0 to 255
    Float16 = 3  # 16-bit IEEE float
    Float32 = 4  # 32-bit IEEE float
    U16 = 5  # Unsigned 16-bit

    def native_size_bytes(self):
        if self in [VecCompFmt.Byte_0_1, VecCompFmt.Byte_Minus1_1, VecCompFmt.Byte_0_255]:
            return 1
        elif self in [VecCompFmt.Float16, VecCompFmt.U16]:
            return 2
        elif self == VecCompFmt.Float32:
            return 4
        raise RuntimeError(f"Nonexistent VecCompFmt called size_bytes: {self}")

    # def numpy_native_dtype(self, big_endian: bool):
    #     if self in [VecCompFmt.Byte_0_1, VecCompFmt.Byte_Minus1_1, VecCompFmt.Byte_0_255]:
    #         return np.uint8
    #     elif self == VecCompFmt.U16:
    #         return BIG_ENDIAN_U16 if big_endian else LITTLE_ENDIAN_U16
    #     elif self == VecCompFmt.Float16:
    #         return BIG_ENDIAN_F16 if big_endian else LITTLE_ENDIAN_F16
    #     elif self == VecCompFmt.Float32:
    #         return BIG_ENDIAN_F32 if big_endian else LITTLE_ENDIAN_F32
    #     raise RuntimeError(f"Nonexistent VecCompFmt called numpy_native_dtype: {self}")

    # def numpy_transformed_dtype(self):
    #     if self == VecCompFmt.Byte_0_255:
    #         return np.uint8
    #     elif self == VecCompFmt.U16:
    #         return np.uint16
    #     else:
    #         # Upgrade Float16 to Float32 so we can manipulate it without rounding error
    #         return np.float32


@dataclass(frozen=True)
class VecStorage:
    comp_fmt: VecCompFmt
    n_comps: int

    def __post_init__(self):
        assert 1 <= self.n_comps <= 4

    def native_size_bytes(self):
        return self.comp_fmt.native_size_bytes() * self.n_comps

    # def numpy_native_dtype(self, big_endian: bool):
    #     return np.dtype((self.comp_fmt.numpy_native_dtype(big_endian), self.n_comps))

    # def numpy_transformed_dtype(self):
    #     return np.dtype((self.comp_fmt.numpy_transformed_dtype(), self.n_comps))

    # def preallocate(self, n_vertices: int) -> np.ndarray:
    #     return np.zeros(
    #         n_vertices,
    #         dtype=self.numpy_transformed_dtype(),
    #     )

    # def transform_native_fmt_array(self, src: np.ndarray) -> np.ndarray:
    #     expected_dtype = self.comp_fmt.numpy_transformed_dtype()
    #     if self.comp_fmt in [VecCompFmt.Byte_0_255, VecCompFmt.U16, VecCompFmt.Float16, VecCompFmt.Float32]:
    #         # Always make a copy, even if the byte order is the same as we want.
    #         # The Blender side wants to do bone remapping etc. so we want a mutable version.
    #         # src is backed by `bytes` -> is immutable.
    #         # Float16 gets upgraded to float32 on transform to avoid rounding errors, so use same_kind instead of equiv
    #         return src.astype(expected_dtype, casting='same_kind', copy=True)
    #     elif self.comp_fmt == VecCompFmt.Byte_0_1:
    #         # src must have dtype == vector of uint8
    #         # it's always safe to cast uint8 -> float16 and float32, they can represent all values
    #         data = src.astype(expected_dtype, casting='safe')
    #         # (0, 255) -> (0, 1) by dividing by 255
    #         data = data / 255.0
    #         return data
    #     elif self.comp_fmt == VecCompFmt.Byte_Minus1_1:
    #         # src must have dtype == vector of uint8
    #         # it's always safe to cast uint8 -> float16 and float32, they can represent all values
    #         data = src.astype(expected_dtype, casting='safe')
    #         # (0, 255) -> (0, 1) by dividing by 255
    #         # (0, 1) -> (-1, 1) by multiplying by 2, subtracting 1
    #         data = ((data / 255.0) * 2.0) - 1.0
    #         return data
    #     raise RuntimeError(f"Invalid VecStorage called transform_native_fmt_array: {self}")

    # def untransform_array(self, big_endian: bool, transformed: np.ndarray) -> np.ndarray:
    #     expected_dtype = self.comp_fmt.numpy_native_dtype(big_endian)
    #     if self.comp_fmt in [VecCompFmt.Byte_0_255, VecCompFmt.U16, VecCompFmt.Float16, VecCompFmt.Float32]:
    #         if transformed.dtype == expected_dtype:  # If the byte order is the same, passthru
    #             return transformed
    #         else:  # else make a copy with transformed byte order
    #             # Float16 is transformed as float32 to avoid rounding errors, so use same_kind instead of equiv
    #             return transformed.astype(expected_dtype, casting='same_kind')
    #     elif self.comp_fmt == VecCompFmt.Byte_0_1:
    #         # (0, 1) -> (0, 255) by multiplying by 255
    #         data = transformed * 255.0
    #         # Do rounding here because the cast doesn't do it right
    #         np.around(data, out=data)
    #         # storage = float, casting to int cannot preserve values -> use 'unsafe'
    #         return data.astype(expected_dtype, casting='unsafe')
    #     elif self.comp_fmt == VecCompFmt.Byte_Minus1_1:
    #         # (-1, 1) to (0, 1) by adding 1, dividing by 2
    #         # (0, 1) to (0, 255) by multiplying by 255
    #         data = ((transformed + 1.0) / 2.0) * 255.0
    #         # Do rounding here because the cast doesn't do it right
    #         np.around(data, out=data)
    #         # storage = float, casting to int cannot preserve values -> use 'unsafe'
    #         return data.astype(expected_dtype, casting='unsafe')
    #     raise RuntimeError(f"Invalid VecStorage called transform_native_fmt_array: {self}")


# VertexBufferLayouts are external dependencies (shaders have a fixed layout, which we can't control) so they are frozen
@dataclass(frozen=True, init=True)
class GMDVertexBufferLayout:
    pos_storage: VecStorage
    weights_storage: Optional[VecStorage]
    bones_storage: Optional[VecStorage]
    normal_storage: Optional[VecStorage]
    tangent_storage: Optional[VecStorage]
    unk_storage: Optional[VecStorage]
    col0_storage: Optional[VecStorage]
    col1_storage: Optional[VecStorage]
    uv_storages: Tuple[VecStorage, ...] # max length 8

    packing_flags: int

    @staticmethod
    def build_vertex_buffer_layout_from_flags(vertex_packing_flags: int, checked: bool = True) -> 'GMDVertexBufferLayout':
        # This derived from the 010 template
        # Bit-checking logic - keep track of the bits we examine, to ensure we don't miss anything
        if checked:
            touched_packing_bits: Set[int] = set()

            def touch_bits(bit_indices: Iterable[int]):
                touched_bits = set(bit_indices)
                touched_packing_bits.update(touched_bits)
        else:
            def touch_bits(bit_indices: Iterable[int]):
                pass

        # Helper for extracting a bitrange start:length and marking those bits as touched.
        def extract_bits(start, length):
            touch_bits(range(start, start + length))

            # Extract bits by shifting down to start and generating a mask of `length` 1's in binary
            # TODO that is the worst possible way to generate that mask.
            return (vertex_packing_flags >> start) & int('1' * length, 2)

        # Helper for extracting a bitmask and marking those bits as touched.
        def extract_bitmask(bitmask):
            touch_bits([i for i in range(32) if ((bitmask >> i) & 1)])

            return vertex_packing_flags & bitmask

        # If the given vector type is `en`abled, extract the bits start:start+2 and find the VecStorage they refer to.
        # If the vector uses full-precision float components, the length is set by `full_precision_n_comps`.
        # If the vector uses byte-size components, the format of those bytes is set by `byte_fmt`.
        def extract_vector_type(en: bool, start: int,
                                full_precision_n_comps: int, byte_fmt: VecCompFmt) -> Optional[VecStorage]:
            bits = extract_bits(start, 2)
            if en:
                if bits == 0:
                    # Float32
                    comp_fmt = VecCompFmt.Float32
                    n_comps = full_precision_n_comps
                elif bits == 1:
                    # Float16
                    comp_fmt = VecCompFmt.Float16
                    n_comps = 4
                else:
                    # Some kind of fixed
                    comp_fmt = byte_fmt
                    n_comps = 4
                return VecStorage(comp_fmt, n_comps)
            else:
                return None

        # pos can be (3 or 4) * (half or full) floats
        pos_count = extract_bits(0, 3)
        pos_precision = extract_bits(3, 1)
        pos_storage = VecStorage(
            comp_fmt=VecCompFmt.Float16 if pos_precision == 1 else VecCompFmt.Float32,
            n_comps=3 if pos_count == 3 else 4
        )

        weight_en = extract_bitmask(0x70)
        weights_storage = extract_vector_type(weight_en, 7, full_precision_n_comps=4, byte_fmt=VecCompFmt.Byte_0_1)

        bones_en = extract_bitmask(0x200)
        bones_storage = VecStorage(VecCompFmt.Byte_0_255, 4) if bones_en else None

        normal_en = extract_bitmask(0x400)
        normal_storage = extract_vector_type(normal_en, 11, full_precision_n_comps=3,
                                             byte_fmt=VecCompFmt.Byte_Minus1_1)

        tangent_en = extract_bitmask(0x2000)
        # Previously this was unpacked with 0_1 because it was arbitrary data.
        # We interpret it as [-1,1] here, and assume it's always equal to the actual tangent.
        # This is usually a good assumption because basically everything needs normal maps, especially character models
        tangent_storage = extract_vector_type(tangent_en, 14, full_precision_n_comps=3,
                                              byte_fmt=VecCompFmt.Byte_Minus1_1)

        unk_en = extract_bitmask(0x0001_0000)
        unk_storage = extract_vector_type(unk_en, 17, full_precision_n_comps=3, byte_fmt=VecCompFmt.Byte_0_1)

        # TODO: Are we sure these bits aren't used for something?
        touch_bits((19, 20))

        # col0 is diffuse and opacity for GMD versions up to 0x03000B
        col0_en = extract_bitmask(0x0020_0000)
        col0_storage = extract_vector_type(col0_en, 22, full_precision_n_comps=4, byte_fmt=VecCompFmt.Byte_0_1)

        # col1 is specular for GMD versions up to 0x03000B
        col1_en = extract_bitmask(0x0100_0000)
        col1_storage = extract_vector_type(col1_en, 25, full_precision_n_comps=4, byte_fmt=VecCompFmt.Byte_0_1)

        # Extract the uv_enable and uv_count bits, to fill out the first 32 bits of the flags
        uv_en = extract_bits(27, 1)
        uv_count = extract_bits(28, 4)
        uv_storages = []
        if uv_count:
            if uv_en:
                # Iterate over all uv bits, checking for active UV slots
                for i in range(8):
                    uv_slot_bits = extract_bits(32 + (i * 4), 4)
                    if uv_slot_bits == 0xF:
                        continue

                    # format_bits is a value between 0 and 3
                    format_bits = (uv_slot_bits >> 2) & 0b11
                    if format_bits in [2, 3]:
                        uv_storages.append(VecStorage(VecCompFmt.Byte_0_1, 4))
                    else:  # format_bits are 0 or 1
                        bit_count_idx = uv_slot_bits & 0b11
                        bit_count = (2, 3, 4, 1)[bit_count_idx]

                        # Component format is float16 or float32
                        uv_comp_fmt = VecCompFmt.Float16 if format_bits else VecCompFmt.Float32

                        # if bit_count == 1:
                        #     error.fatal(f"UV with 1 element encountered - unsure how to proceed")
                        # else:
                        uv_storages.append(VecStorage(uv_comp_fmt, n_comps=bit_count))

                    if len(uv_storages) == uv_count:
                        # Touch the rest of the bits
                        touch_bits(range(32 + ((i + 1) * 4), 64))
                        break

                # if len(uv_storages) != uv_count:
                #     error.recoverable(
                #         f"Layout Flags {vertex_packing_flags:016x} claimed to have {uv_count} UVs "
                #         f"but specified {len(uv_storages)}")
            else:
                # Touch all of the uv bits, without doing anything with them
                touch_bits(range(32, 64))
                print(
                    f"Layout Flags {vertex_packing_flags:016x} claimed to have {uv_count} UVs "
                    f"but UVs are disabled", file=sys.stderr)
        else:
            # No UVs at all
            touch_bits(range(32, 64))
            uv_storages = []
            pass

        # print(uv_storages)

        if checked:
            expected_touched_bits = {x for x in range(64)}
            if touched_packing_bits != expected_touched_bits:
                raise ValueError(
                    f"Incomplete vertex format parse - "
                    f"bits {expected_touched_bits - touched_packing_bits} were not touched")

        return GMDVertexBufferLayout(
            pos_storage=pos_storage,
            weights_storage=weights_storage,
            bones_storage=bones_storage,
            normal_storage=normal_storage,
            tangent_storage=tangent_storage,
            unk_storage=unk_storage,
            col0_storage=col0_storage,
            col1_storage=col1_storage,
            uv_storages=tuple(uv_storages),

            packing_flags=vertex_packing_flags,
        )
