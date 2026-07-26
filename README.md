# MRI Pipeline

Command-line pipeline for organizing and preprocessing brain MRI data, with a focus on FLAIR images, lesion masks, white matter masks, and Pre/Post comparison workflows.

The main entry point is:

```bash
python run_pipeline.py run --input "/path/to/input" --output "/path/to/output" --steps STEP_1 STEP_2
```

Most settings live in `config.yaml`; input and output roots are provided from the command line.

## Features

- Organize MRI files by timepoint and sequence.
- Preprocess FLAIR images with N4 correction, registration, skull stripping, and intensity normalization.
- Save and reuse registration transforms.
- Create histogram-matched Pre/Post difference images.
- Segment lesion masks with FLAMeS.
- Generate white matter masks with SynthSeg.
- Clean manual ROI masks using white matter and exclusion masks.
- Organize normalized outputs into Pre and Post folders.

## Installation

Clone the repository and install the Python requirements:

```bash
cd /path/to/MRI_pipeline
pip install -r requirements.txt
```

Check the CLI:

```bash
python run_pipeline.py --help
```

Some steps require external tools:

- `hd-bet` for skull stripping.
- FLAMeS / nnU-Net v2 for lesion segmentation.
- SynthSeg for white matter segmentation.

These tools are not included in the repository. Configure their local paths in `config.yaml`.

## Recommended Input Layout

The cleanest input structure is:

```text
Input/
  Patients/
    Patient_001/
      Pre/
        Patient_001_FLAIR.nii.gz
      Post/
        Patient_001_FLAIR.nii.gz
    Patient_002/
      Pre/
        Patient_002_FLAIR.nii.gz
      Post/
        Patient_002_FLAIR.nii.gz

  Transforms/
    Pre_Transformations/
      Patient_001/
        existing_pre_transform.tfm
    Post_Transformations/
      Patient_001/
        existing_post_transform.tfm
```

`Transforms/` is optional. If a transform is found, it is reused. If not, the pipeline estimates a new registration transform and saves it under the output folder.

Single patient folders and single NIfTI files are also supported for preprocessing and some segmentation steps.

## Configuration

Before running registration, set the atlas/reference image:

```yaml
run:
  preprocess_flair:
    atlas_path: "/path/to/reference_or_atlas_FLAIR.nii.gz"
```

Configure external tools:

```yaml
run:
  flames:
    root: "/path/to/FLAMeS"

  synthseg:
    python_executable: "/path/to/synthseg/python"
    script_path: "/path/to/SynthSeg_predict.py"
    version: "auto"
```

Folder names, timepoint names, sequence names, transform behavior, normalization methods, and histogram matching settings are also controlled in `config.yaml`.

## Common Commands

Run the default workflow from `config.yaml`:

```bash
python run_pipeline.py run --input "/data/Input" --output "/data/Output"
```

Run FLAIR preprocessing:

```bash
python run_pipeline.py run --input "/data/Input" --output "/data/Output" --steps preprocess-flair
```

Override preprocessing steps:

```bash
python run_pipeline.py run --input "/data/Input" --output "/data/Output" --steps preprocess-flair --preprocess-steps n4 registration skull-strip normalization
```

Run preprocessing, difference images, and normalization organization:

```bash
python run_pipeline.py run --input "/data/Input" --output "/data/Output" --steps preprocess-flair make-diff-images split-normalizations --preprocess-steps n4 registration skull-strip normalization
```

Create a standalone difference image from two files:

```bash
python run_pipeline.py make-diff-images --reference "/data/Pre_FLAIR.nii.gz" --source "/data/Post_FLAIR.nii.gz" --output "/data/Diff_Output"
```

Segment Pre/existing lesions with FLAMeS:

```bash
python run_pipeline.py segment-pre-lesions --input "/data/Preprocessed_FLAIR" --output "/data/Output"
```

Segment lesions with FLAMeS into a custom output folder:

```bash
python run_pipeline.py segment-lesions --input "/data/Post_FLAIR_brain" --output "/data/Output" --lesion-folder "Post_FLAMeS"
```

Generate white matter masks with SynthSeg:

```bash
python run_pipeline.py run --input "/data/Preprocessed_FLAIR" --output "/data/Output" --steps segment-white-matter --registered-only
```

Organize normalized images:

```bash
python run_pipeline.py run --input "/data/Preprocessed_FLAIR" --output "/data/Output" --steps split-normalizations
```

Clean manual ROI masks, such as manually segmented new lesions:

```bash
python run_pipeline.py clean-roi-masks --roi-root "/data/Lesions/New_Manual" --allowed-root "/data/Masks/White_Matter" --exclusion-root "/data/Lesions/Existing_Pre" --output "/data/Lesions/New_Cleaned"
```

Use `--exclusion-dilation 0` to remove only overlapping voxels. Use `--exclusion-dilation 1` to also remove voxels touching the exclusion mask.

## Pipeline Steps

Available `run --steps` values:

```text
split-sequences
preprocess-flair
make-diff-images
split-normalizations
segment-pre-lesions
segment-lesions
segment-white-matter
```

Standalone ROI cleaning command:

```text
clean-roi-masks
```

Step order matters. For a full FLAIR/lesion workflow, a practical order is:

```text
preprocess-flair
make-diff-images
segment-pre-lesions
segment-white-matter
split-normalizations
```

Manual new lesion masks can then be cleaned with `clean-roi-masks` before radiomics extraction.

## Output Overview

Typical output:

```text
Output/
  Preprocessed_FLAIR/
  Difference_Images/
  Lesions/
    Existing_Pre/
    Post_FLAMeS/
    New_Cleaned/
  Masks/
    White_Matter/
  Organized_Pre/
  Organized_Post/
  Transforms/
```

Registration transforms are saved under:

```text
Output/Transforms/Pre_Transformations/Patient_ID/
Output/Transforms/Post_Transformations/Patient_ID/
```

## Notes

- Use dummy/example paths in `config.yaml` before sharing the repository publicly.
- Keep personal paths in `config.local.yaml`; this file is ignored by Git.
- Large data files, models, NIfTI images, transforms, and tool folders should not be committed to Git.
- `tools/` can be used locally for FLAMeS or SynthSeg, but it should remain ignored by Git.
- HD-BET, nnU-Net, FLAMeS, and SynthSeg may print their own progress messages.

## Image processing and segmentation

Brain extraction (skull stripping) was performed using **HD-BET**. Anatomical brain segmentation was performed using **SynthSeg**, while multiple sclerosis lesion segmentation was performed using **FLAMeS**, which is based on the **nnU-Net** framework.

This repository does not redistribute the source code, pretrained models, or model weights associated with HD-BET, SynthSeg, FLAMeS, or nnU-Net. These tools were used only for image processing and for generating the corresponding brain and lesion segmentation masks.

## References

* Isensee, F., Schell, M., Tursunova, I., Brugnara, G., Bonekamp, D., Neuberger, U., Wick, A., Schlemmer, H. P., Heiland, S., Wick, W., Bendszus, M., Maier-Hein, K. H., & Kickingereder, P. (2019). Automated brain extraction of multisequence MRI using artificial neural networks. *Human Brain Mapping, 40*(17), 4952-4964. https://doi.org/10.1002/hbm.24750

* Billot, B., Greve, D. N., Puonti, O., Thielscher, A., Van Leemput, K., Fischl, B., Dalca, A. V., & Iglesias, J. E. (2023). SynthSeg: Segmentation of brain MRI scans of any contrast and resolution without retraining. *Medical Image Analysis, 86*, 102789. https://doi.org/10.1016/j.media.2023.102789

* Dereskewicz, E., La Rosa, F., Dos Santos Silva, J., et al. (2025). A novel convolutional neural network for automated multiple sclerosis brain lesion segmentation. *Journal of Neuroimaging, 35*(5), e70085. https://doi.org/10.1111/jon.70085

* Isensee, F., Jaeger, P. F., Kohl, S. A. A., Petersen, J., & Maier-Hein, K. H. (2021). nnU-Net: A self-configuring method for deep learning-based biomedical image segmentation. *Nature Methods, 18*(2), 203-211. https://doi.org/10.1038/s41592-020-01008-z

## Troubleshooting

If no files are created, check:

- The input path exists.
- The input contains `.nii` or `.nii.gz` files.
- Folder names match the configured `Pre` and `Post` timepoints.
- Sequence and normalization names match `config.yaml`.
- External tool paths in `config.yaml` are correct.

If registration fails, check the atlas path and existing transform paths.

If SynthSeg runs on CPU instead of GPU, test the configured Python environment directly:

```bash
python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"
```
