from pathlib import Path

import SimpleITK as sitk

from mri_pipeline.utils.files import ensure_dir


def create_nawm_mask(wm_path, lesion_path, output_path):
    wm_path = Path(wm_path)
    lesion_path = Path(lesion_path)
    output_path = Path(output_path)

    wm = sitk.ReadImage(str(wm_path), sitk.sitkUInt8)
    lesion = sitk.ReadImage(str(lesion_path), sitk.sitkUInt8)

    if wm.GetSize() != lesion.GetSize():
        raise ValueError(
            f"WM and lesion masks must have the same size. "
            f"WM: {wm.GetSize()}, lesion: {lesion.GetSize()}"
        )

    nawm = sitk.Cast((wm > 0) & ~(lesion > 0), sitk.sitkUInt8)

    ensure_dir(output_path.parent)
    sitk.WriteImage(nawm, str(output_path))

    return output_path


def create_nawm_masks(
    wm_root,
    lesion_root,
    output_root,
    wm_pattern="*_wm_mask.nii.gz",
    lesion_pattern="*_mask_thr0.nii",
):
    wm_root = Path(wm_root)
    lesion_root = Path(lesion_root)
    output_root = Path(output_root)

    if not wm_root.exists() or not wm_root.is_dir():
        raise FileNotFoundError(f"WM folder not found: {wm_root}")

    if not lesion_root.exists() or not lesion_root.is_dir():
        raise FileNotFoundError(f"Lesion map folder not found: {lesion_root}")

    created_files = []
    patient_dirs = sorted(
        path for path in wm_root.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )

    print(f"{len(patient_dirs)} WM patient folders found.")

    for patient_dir in patient_dirs:
        patient_id = patient_dir.name
        lesion_dir = lesion_root / patient_id

        print(f"NAWM mask: {patient_id}")

        if not lesion_dir.exists() or not lesion_dir.is_dir():
            print(f"  [Warning] No lesion folder found for {patient_id}. Skipping.")
            continue

        wm_files = sorted(patient_dir.glob(wm_pattern))
        lesion_files = sorted(lesion_dir.glob(lesion_pattern))

        if not wm_files:
            print(f"  [Warning] No WM mask found for {patient_id}. Skipping.")
            continue

        if not lesion_files:
            print(f"  [Warning] No lesion mask found for {patient_id}. Skipping.")
            continue

        wm_path = wm_files[0]
        lesion_path = lesion_files[0]
        output_path = (
            output_root
            / patient_id
            / wm_path.name.replace("_wm_mask.nii.gz", "_nawm_mask.nii.gz")
        )

        if output_path.exists():
            print(f"  [Skip] Exists: {output_path.name}")
            continue

        try:
            created_file = create_nawm_mask(
                wm_path=wm_path,
                lesion_path=lesion_path,
                output_path=output_path,
            )
        except Exception as exc:
            print(f"  [Error] Failed for {patient_id}: {exc}")
            continue

        created_files.append(created_file)
        print(f"  -> Created: {created_file}")

    return created_files
