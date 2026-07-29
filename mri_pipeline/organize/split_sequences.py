import shutil
from pathlib import Path
from mri_pipeline.utils.files import is_nifti, ensure_dir, get_patient_dirs, list_nifti_files

try:
    from tqdm.auto import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable


def find_sequence_files(folder_path, sequence_name):
    folder = Path(folder_path)
    if not folder.exists() or not folder.is_dir():
        return []
    

    matched_files = []
    seq = sequence_name.lower()
    for file in folder.iterdir():
        fname = file.name.lower()
        if not file.is_file() or fname.startswith("."):
            continue

        if seq in fname:
            if is_nifti(file) or fname.endswith(".json"):
                matched_files.append(file)

    return sorted(matched_files)

def transfer_file(src, dst, copy_mode=True):
    src = Path(src)
    dst = Path(dst)
    ensure_dir(dst.parent)

    if copy_mode:
        shutil.copy2(src, dst)
    else:
        shutil.move(src, dst)

    return dst

def organize_mri_files(
    input_root,
    output_root,
    timepoints,
    sequences,
    copy_files=True,
):

    input_root = Path(input_root)
    output_root = Path(output_root)

    if not input_root.exists() or not input_root.is_dir():
        raise FileNotFoundError(f"Folder doesn't exist: {input_root}")
    
    created_files = []
    if any((input_root / tp).is_dir() for tp in timepoints):
        patient_folders = [input_root]
    else:
        patient_folders = get_patient_dirs(input_root)

    if not patient_folders:
        root_files = list_nifti_files(input_root)
        if root_files:
            patient_folders = [input_root]
    print(f"{len(patient_folders)} patient folders found.\n")

    for patient_folder in tqdm(patient_folders, desc="Split sequences patients", unit="patient"):
        patient_id = patient_folder.name
        print(f"Patient processing: {patient_id}")
        patient_timepoints = []
        for tp in timepoints:
            tp_folder = patient_folder / tp

            if tp_folder.exists() and tp_folder.is_dir():
                patient_timepoints.append((tp, tp_folder))
        
        if not patient_timepoints:
            patient_timepoints.append(("Pre", patient_folder))

        for tp, tp_folder in patient_timepoints:
            if not tp_folder.exists() or not tp_folder.is_dir():
                print(f"  [Warning] No folder was found: {tp_folder}")
                continue

            for seq in sequences:
                matched_files = find_sequence_files(tp_folder, seq)

                if not matched_files:
                    print(f"  [INFO] No records were found for {tp}_{seq}")
                    continue

                destination_patient_folder = output_root / f"{tp}_{seq}" / patient_id
                ensure_dir(destination_patient_folder)

                print(f"  {tp}_{seq}: {len(matched_files)} files found")

                for src_file in matched_files:
                    dst_file = destination_patient_folder / src_file.name
                    created_file = transfer_file(src_file, dst_file, copy_mode=copy_files)
                    created_files.append(created_file)
                    print(f"    -> {'Copied' if copy_files else 'Moved'}: {src_file.name}")

        print()

    print("The organization was successfully completed.")

    return created_files
    
