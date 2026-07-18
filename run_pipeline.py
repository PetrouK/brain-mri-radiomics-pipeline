import argparse
from pathlib import Path

from mri_pipeline.utils.config import load_config
from mri_pipeline.utils.files import ensure_dir, is_nifti
from mri_pipeline.organize.split_sequences import organize_mri_files
from mri_pipeline.organize.split_normalizations import organize_by_normalization
from mri_pipeline.preprocessing.flair_pipeline import (
    build_registration_transform_path,
    find_patient_transform,
    preprocess_flair_folder,
    run_flair_pipeline,
)

from mri_pipeline.preprocessing.diff_images import (
    create_flair_difference_images,
    create_registered_difference_pair,
)

try:
    from tqdm.auto import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable


RUN_STEPS = [
    "split-sequences",
    "preprocess-flair",
    "make-diff-images",
    "split-normalizations",
]

PREPROCESS_STEPS = [
    "n4",
    "registration",
    "skull-strip",
    "diff",
    "normalization",
]

def build_parser():
    parser = argparse.ArgumentParser(description="MRI pipeline")

    parser.add_argument(
        "command",
        choices=[
            "split-sequences",
            "split-normalizations",
            "preprocess-flair",
            "make-diff-images",
            "make-synthseg-masks",
            "make-nawm-masks",
            "run",
        ],
        help="Pipeline step to run",
    )

    parser.add_argument(
        "--input",
        help = "Path of input file or folder"
    )

    parser.add_argument(
        "--output",
        help = "Path of output file or folder"
    )

    parser.add_argument(
        "--steps",
        nargs= "+",
        choices=RUN_STEPS,
        help = "Processing steps"
    )

    parser.add_argument(
        "--preprocess-steps",
        nargs="+",
        choices=PREPROCESS_STEPS,
        help="Override FLAIR preprocessing steps for this run.",
    )

    parser.add_argument(
        "--diff-register-missing",
        action="store_true",
        help="Register missing Pre/Post pairs before creating difference images.",
    )

    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config YAML file",
    )

    parser.add_argument(
        "--move",
        action="store_true",
        help="Move files instead of copying them",
    )

    parser.add_argument(
        "--mode",
        choices=["one-file", "folder"],
        default=None,
        help="Preprocessing mode for preprocess-flair.",
    )

    parser.add_argument(
        "--reference",
        help="Reference image for standalone difference image creation.",
    )

    parser.add_argument(
        "--source",
        help="Source image for standalone difference image creation.",
    )

    return parser

def infer_patient_and_timepoint(image_path, timepoints_config):
    image_path = Path(image_path)
    parent = image_path.parent
    pre_name = timepoints_config.get("pre", "Pre")
    post_name = timepoints_config.get("post", "Post")
    timepoint_names = {pre_name.lower(): pre_name, post_name.lower(): post_name}

    if parent.name.lower() in timepoint_names:
        return parent.parent.name, timepoint_names[parent.name.lower()]

    return parent.name, pre_name


def run_flair_file_preprocessing(
    image_path,
    output_preprocessed,
    output_transforms,
    timepoints_config,
    transforms_config,
    flair_config,
    preprocess_steps,
):
    image_path = Path(image_path)

    if not image_path.exists() or not image_path.is_file() or not is_nifti(image_path):
        raise FileNotFoundError(f"Input FLAIR image not found: {image_path}")

    patient_id, timepoint = infer_patient_and_timepoint(image_path, timepoints_config)
    output_dir = ensure_dir(Path(output_preprocessed) / patient_id / timepoint)

    pre_name = timepoints_config.get("pre", "Pre")
    transform_folder = (
        transforms_config["pre_folder"]
        if timepoint.lower() == pre_name.lower()
        else transforms_config["post_folder"]
    )
    transform_root = Path(output_transforms) / transform_folder

    if transforms_config.get("overwrite", False):
        transform_path = None
    else:
        transform_path = find_patient_transform(transform_root, patient_id)

    save_transform_path = None
    if transforms_config.get("save", True):
        save_transform_path = build_registration_transform_path(
            transform_root,
            patient_id,
            image_path,
        )

    return run_flair_pipeline(
        image_path=image_path,
        steps=preprocess_steps or flair_config["steps"],
        reference_path=flair_config["atlas_path"],
        transform_path=transform_path,
        save_transform_path=save_transform_path,
        output_dir=output_dir,
        normalization_methods=flair_config.get("normalization_methods", []),
    )


def run_pipeline_steps(config, 
                       input_root, 
                       output_root, 
                       steps, 
                       copy_files=True, 
                       preprocess_steps=None,
                       diff_register_missing=False,
                       ):
    
    run_config = config["run"]
    folders_config = run_config["folders"]
    timepoints_config = run_config["timepoints"]
    transforms_config = run_config["transforms"]
    flair_config = run_config["preprocess_flair"]
    diff_config = run_config.get("difference_images", {})

    input_root = Path(input_root)
    output_root = Path(output_root)

    output_seq = output_root / folders_config["split_sequences"]
    output_preprocessed = output_root / folders_config["preprocessed_flair"]
    output_diff = output_root / folders_config["difference_images"]
    output_organized_pre = output_root / folders_config["organized_pre"]
    output_organized_post = output_root / folders_config["organized_post"]
    output_transforms = output_root / folders_config["transforms"]

    summary = {}

    for step in tqdm(steps, desc="Run steps", unit="step"):
        if step == "split-sequences":
            created_files = organize_mri_files(
                input_root,
                output_seq,
                list(timepoints_config.values()),
                run_config["sequences"],
                copy_files=copy_files,
            )
            summary[step] = created_files

        if step == "preprocess-flair":
            if input_root.is_file():
                created_files = run_flair_file_preprocessing(
                    image_path=input_root,
                    output_preprocessed=output_preprocessed,
                    output_transforms=output_transforms,
                    timepoints_config=timepoints_config,
                    transforms_config=transforms_config,
                    flair_config=flair_config,
                    preprocess_steps=preprocess_steps,
                )
            else:
                patients_folder = folders_config.get("patients")
                preprocessing_input = input_root

                if patients_folder is not None and (input_root / patients_folder).is_dir():
                    preprocessing_input = input_root / patients_folder

                created_files = preprocess_flair_folder(
                    input_root=preprocessing_input,
                    output_root=output_preprocessed,
                    atlas_path=flair_config["atlas_path"],
                    pre_transform_root=output_transforms / transforms_config["pre_folder"],
                    post_transform_root=output_transforms / transforms_config["post_folder"],
                    input_pre_transform_root=input_root / folders_config["transforms"] / transforms_config["pre_folder"],
                    input_post_transform_root=input_root / folders_config["transforms"] / transforms_config["post_folder"],
                    diff_output_root=output_diff,
                    timepoints=timepoints_config,
                    sequence=flair_config.get("sequence", "FLAIR"),
                    steps=preprocess_steps or flair_config["steps"],
                    normalization_methods=flair_config.get("normalization_methods", []),
                    save_transforms=transforms_config.get("save", True),
                    overwrite_transforms=transforms_config.get("overwrite", False),
                )
            summary[step] = created_files

        if step == "split-normalizations":
            if "preprocess-flair" in summary:
                normalization_source = output_preprocessed
            else:
                normalization_source = input_root

            created_files = organize_by_normalization(
                source_root=normalization_source,
                normalizations=run_config["normalizations"],
                copy_files=copy_files,
                pre_target_root=output_organized_pre,
                post_target_root=output_organized_post,
            )

            if not created_files:
                raise ValueError(f"No normalized files found in {normalization_source}. Check that filenames contain one of the configured normalizations: {run_config['normalizations']}")
            summary[step] = created_files

        if step == "make-diff-images":
            diff_config = run_config.get("difference_images", {})

            if "preprocess-flair" in summary:
                difference_source = output_preprocessed
            else:
                difference_source = input_root

            created_files = create_flair_difference_images(
                preprocessed_root=difference_source,
                output_root=output_root / folders_config["difference_images"],
                pre_timepoint=timepoints_config.get("pre", "Pre"),
                post_timepoint=timepoints_config.get("post", "Post"),
                histogram_levels=diff_config.get("histogram_levels", 512),
                match_points=diff_config.get("match_points", 10),
                threshold_at_mean=diff_config.get("threshold_at_mean", True),
                register_missing=diff_register_missing,
            )

            summary[step] = created_files
            
    return summary


def summarize_run(summary):
    counts = {}

    for step, result in summary.items():
        if isinstance(result, list):
            counts[step] = len(result)
        else:
            counts[step] = 1

    return counts


def main():
    parser = build_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    copy_files = not args.move

    if args.command == "run":
        if not args.input:
            parser.error("run requires --input")
        if not args.output:
            parser.error("run requires --output")

        steps = args.steps or config["run"].get("default_steps", RUN_STEPS)

        summary = run_pipeline_steps(
            config=config,
            input_root=args.input,
            output_root=args.output,
            steps=steps,
            copy_files=copy_files,
            preprocess_steps=args.preprocess_steps,
            diff_register_missing=args.diff_register_missing,
        )
        print("Run complete.")
        print(summarize_run(summary))
        return

    if args.command == "split-sequences":
        created_files = organize_mri_files(
            input_root=config["raw_root"],
            output_root=config["split_sequences_output_root"],
            timepoints=config["timepoints"],
            sequences=config["sequences"],
            copy_files=copy_files,
        )

        print(f"Created {len(created_files)} files.")
        return

    if args.command == "split-normalizations":
        created_files = organize_by_normalization(
            source_root=config["pre_flair_root"],
            target_root=config["organized_pre_root"],
            normalizations=config["normalizations"],
            copy_files=copy_files,
        )

        print(f"Created {len(created_files)} files.")
        return

    if args.command == "preprocess-flair":
        mode = args.mode or config.get("preprocess_mode", "one-file")

        if mode == "one-file":
            from mri_pipeline.preprocessing.flair_pipeline import run_flair_pipeline

            one_file_config = config["preprocess_one_file"]

            if one_file_config.get("image_path") is None:
                raise ValueError("Set preprocess_one_file.image_path in config.yaml before running one-file mode.")

            results = run_flair_pipeline(
                image_path=one_file_config["image_path"],
                steps=one_file_config["steps"],
                reference_path=one_file_config.get("reference_path"),
                transform_path=one_file_config.get("transform_path"),
                output_dir=one_file_config.get("output_dir"),
                mask_path=one_file_config.get("mask_path"),
                normalization_methods=one_file_config.get("normalization_methods", []),
            )

        elif mode == "folder":
            from mri_pipeline.preprocessing.flair_pipeline import preprocess_flair_folder

            folder_config = config["preprocess_folder"]

            results = preprocess_flair_folder(
                input_root=folder_config["input_root"],
                output_root=folder_config["output_root"],
                atlas_path=folder_config["atlas_path"],
                pre_transform_root=folder_config.get("pre_transform_root"),
                post_transform_root=folder_config.get("post_transform_root"),
                timepoints=folder_config.get("timepoints", {}),
                sequence=folder_config.get("sequence", "FLAIR"),
                steps=folder_config["steps"],
                normalization_methods=folder_config.get("normalization_methods", []),
                save_transforms=folder_config.get("save_transforms", True),
                overwrite_transforms=folder_config.get("overwrite_transforms", False),
            )

        else:
            raise ValueError(f"Unsupported preprocess mode: {mode}")

        print("Preprocessing complete.")
        print(results)
        return

    if args.command == "make-diff-images":
        if not args.reference:
            parser.error("make-diff-images requires --reference")
        if not args.source:
            parser.error("make-diff-images requires --source")
        if not args.output:
            parser.error("make-diff-images requires --output")

        diff_config = config["run"].get("difference_images", {})

        result = create_registered_difference_pair(
            reference_path=args.reference,
            source_path=args.source,
            output_root=args.output,
            histogram_levels=diff_config.get("histogram_levels", 512),
            match_points=diff_config.get("match_points", 10),
            threshold_at_mean=diff_config.get("threshold_at_mean", True),
            register_if_needed=True,
        )

        print("Difference image complete.")
        print(result)
        return

    if args.command == "make-synthseg-masks":
        from mri_pipeline.preprocessing.synthseg_masks import create_synthseg_masks

        synthseg_config = config["synthseg_masks"]

        created_files = create_synthseg_masks(
            input_root=synthseg_config["input_root"],
            synthseg_root=synthseg_config.get("synthseg_root", config["synthseg_root"]),
            output_roots=synthseg_config["output_roots"],
            regions=synthseg_config.get("regions"),
            patterns=synthseg_config.get("patterns"),
            docker_image=synthseg_config.get("docker_image", "freesurfer/freesurfer:8.2.0"),
            use_gpu=synthseg_config.get("use_gpu", True),
        )

        print(f"Created {len(created_files)} SynthSeg masks.")
        return

    if args.command == "make-nawm-masks":
        from mri_pipeline.preprocessing.nawm import create_nawm_masks

        nawm_config = config["nawm_masks"]

        created_files = create_nawm_masks(
            wm_root=nawm_config["wm_root"],
            lesion_root=nawm_config["lesion_root"],
            output_root=nawm_config["output_root"],
            wm_pattern=nawm_config.get("wm_pattern", "*_wm_mask.nii.gz"),
            lesion_pattern=nawm_config.get("lesion_pattern", "*_mask_thr0.nii"),
        )

        print(f"Created {len(created_files)} NAWM masks.")
        return


if __name__ == "__main__":
    main()
