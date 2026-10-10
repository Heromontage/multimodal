# Anatomical geometry sources

The app uses genuine BodyParts3D release 4.0 OBJ meshes from the official 99%-polygon-reduced IS-A archive. Only selected heart/coronary components were downloaded with HTTP range requests; the entire archive is not bundled. Source geometry is unchanged, with no procedural substitute vessels.

- Dataset/viewer: https://lifesciencedb.jp/bp3d/
- Official archive: https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/isa_BP3D_4.0_obj_99.zip
- Official mesh mapping: https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/partof_element_parts.txt
- Official term list: https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/partof_parts_list_e.txt
- Archive documentation and current license: https://dbarchive.biosciencedbc.jp/data/bodyparts3d/LATEST/README_e.html
- License: https://creativecommons.org/licenses/by/4.0/

## Attribution

BodyParts3D, © The Database Center for Life Science licensed under CC Attribution 4.0 International.

Short UI credit: **BodyParts3D / DBCLS · CC BY 4.0**.

The official archive README was updated in February 2025 to CC BY 4.0. The older live viewer footer still displays CC BY-SA 2.1 Japan; this app specifically obtains release 4.0 assets from the archive whose current README supplies the CC BY 4.0 license.

## Anatomy mapping

| App target | FMA concept | Official name | OBJ elements |
| --- | --- | --- | --- |
| LAD | FMA3862 | anterior interventricular branch of left coronary artery | FJ2631 through FJ2648 |
| LCX | FMA3895 | circumflex branch of left coronary artery | FJ2649 through FJ2654 |
| RCA | FMA50039 | right coronary artery | 29 elements listed individually in manifest.json |
| Heart backdrop | FMA7088 | heart | tissue/valve components FJ2417 through FJ2439, excluding chamber cavity volumes FJ2422–FJ2425 and absent FJ2428 |
| Left coronary trunk | FMA3855 | trunk of left coronary artery | source elements listed in manifest.json |

## Coordinates and use

All OBJ coordinates retain their original common anatomical alignment, in millimetres. The source viewer uses Z as up and views from negative Y for an anterior view. Rotate the entire group by -π/2 around X to use Three.js Y-up; this maps anterior to positive Z. Apply one common centering/scale transform to the complete collection, never center or scale components independently. The manifest records exact bounds, vertex/face counts, and SHA-256 hashes for every file.

The heart backdrop should be somewhat translucent so source coronary vessels remain inspectable. The left coronary trunk has target null and kind artery; it is context, not an independently scored target. Color the LAD/LCX/RCA elements using their target labels while preserving geometry. Each target contains the branches assigned by the official part-of mapping.

These are a reference adult male anatomy model, not patient-specific coronary reconstruction. The source archive has 99% polygon reduction and therefore intentionally coarse geometry. Risk colors are application overlays on anatomical reference meshes and are not measurements of stenosis or lesion locations.
