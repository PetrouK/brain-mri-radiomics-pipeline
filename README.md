# MRI Pipeline

Command-line pipeline for organizing and preprocessing brain MRI data, with a focus on FLAIR images, lesion masks, white matter masks, and Pre/Post comparison workflows.

## Project Aim

The aim of this project is to support radiomics analysis of multiple sclerosis lesions that are visible on Post/follow-up MRI but not visible on the corresponding Pre/baseline MRI.

In this workflow, Post/new lesion masks are expected to be manually segmented. The pipeline provides preprocessing, registration, Pre/Post difference image generation, pre-existing lesion segmentation, white matter segmentation, ROI cleaning, and preparation for downstream radiomics extraction.

Manual segmentation of Post/new lesions should preferably be performed after registration, using the registered Post image in the same spatial space as the Pre/baseline image. This helps ensure that manual Post lesion masks, Pre lesion masks, white matter masks, mirrored healthy ROIs, and radiomics measurements are aligned in a common image space.

## Research Use Notice

This project is intended for research use only. It is not a clinical diagnostic tool and should not be used for clinical decision-making without independent validation.

The workflow has been tested on brain MRI data acquired on a 3 Tesla MRI system.

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
- Mirror lesion masks to create healthy control ROIs.
- Extract PyRadiomics features from any ROI label folder structure.
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

### Radiomics Environment

Radiomics extraction uses PyRadiomics, which is best installed in a separate Python environment. This avoids conflicts with deep learning tools such as HD-BET, FLAMeS, nnU-Net, and SynthSeg.

Recommended setup:

```bash
conda create -n radiomics_env python=3.10 -y
conda activate radiomics_env
pip install -r requirements-radiomics.txt
```

Then run only the radiomics step from this environment:

```bash
python run_pipeline.py extract-radiomics --image-root "/data/Images" --roi-root "/data/ROIs" --discretization-mode binCount --discretization-values 32
```

PyRadiomics `3.0.1` may fail to build on Python `3.12+` because of deprecated build-time configuration code. Use Python `3.10` or `3.11` for the radiomics environment.

## Recommended Manual Segmentation Workflow

For longitudinal lesion radiomics, the recommended order is:

1. Register Pre and Post FLAIR images.
2. Review the registered Post image.
3. Generate Pre lesion masks and white matter masks in the same space.
4. Manually segment Post/new lesions on the registered Post image.
5. Clean manual Post lesion masks using white matter and exclusion masks.
6. Generate and clean mirrored healthy control ROIs.
7. Extract radiomics features from lesion and healthy control ROIs.

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

This writes masks under:

```text
/data/Output/FLAMeS_Lesions/Existing_Pre/
```

Segment lesions with FLAMeS into another named FLAMeS lesion folder:

```bash
python run_pipeline.py segment-lesions --input "/data/Post_FLAIR_brain" --output "/data/Output" --lesion-folder "Post"
```

This writes masks under:

```text
/data/Output/FLAMeS_Lesions/Post/
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
python run_pipeline.py clean-roi-masks --roi-root "/data/Manual_Lesions" --allowed-root "/data/Masks/White_Matter" --exclusion-root "/data/FLAMeS_Lesions/Existing_Pre" --output "/data/Cleaned_ROIs/Lesions"
```

If the allowed, ROI, or exclusion masks are stored in nested `Pre`/`Post` folders, pass the corresponding timepoint. For example, to clean manually segmented Post/new lesion masks using Post white matter masks:

```bash
python run_pipeline.py clean-roi-masks --roi-root "/data/Manual_Lesions" --allowed-root "/data/Masks/White_Matter" --allowed-timepoint Post --exclusion-root "/data/FLAMeS_Lesions/Existing_Pre" --output "/data/Cleaned_ROIs/Lesions"
```

The same command can use Pre white matter masks by changing `--allowed-timepoint Post` to `--allowed-timepoint Pre`. If the folders are not nested by timepoint, omit the timepoint arguments.

Use `--exclusion-dilation 0` to remove only overlapping voxels. Use `--exclusion-dilation 1` to also remove voxels touching the exclusion mask.

Mirror ROI masks, for example to create healthy control ROIs from manually segmented lesion masks:

```bash
python run_pipeline.py mirror-roi-masks --input "/data/Cleaned_ROIs/Lesions" --output "/data/Healthy"
```

Extract radiomics features:

```bash
python run_pipeline.py extract-radiomics --image-root "/data/Images" --roi-root "/data/ROIs" --output "/data/Radiomics" --discretization-mode binCount --discretization-values 32 64 128 --max-workers 8
```

Use direct `binWidth` values:

```bash
python run_pipeline.py extract-radiomics --image-root "/data/Images" --roi-root "/data/ROIs" --output "/data/Radiomics" --discretization-mode binWidth --discretization-values 5 10 20 --max-workers 8
```

Use target bin counts to compute `binWidth` from the average ROI intensity range:

```bash
python run_pipeline.py extract-radiomics --image-root "/data/Images" --roi-root "/data/ROIs" --output "/data/Radiomics" --discretization-mode binWidth --discretization-values 32 64 128 --values-are-target-bins --max-workers 8
```

Radiomics outputs are written as one Excel file per discretization value, for example:

```text
Radiomics/
  Features_binCount_32.xlsx
  Features_binCount_64.xlsx
  Features_binWidth_targetBins_128.xlsx
```

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
mirror-roi-masks
extract-radiomics
```

`clean-roi-masks` supports both flat case folders and timepoint-specific folders:

```text
Masks/White_Matter/
  case_001/
    wm_mask.nii.gz
```

or:

```text
Masks/White_Matter/
  case_001/
    Pre/
      pre_wm_mask.nii.gz
    Post/
      post_wm_mask.nii.gz
```

Use `--roi-timepoint`, `--allowed-timepoint`, or `--exclusion-timepoint` when a selected root contains nested `Pre`/`Post` folders.

Step order matters. For a full FLAIR/lesion workflow, a practical order is:

```text
preprocess-flair
make-diff-images
segment-pre-lesions
segment-white-matter
split-normalizations
```

Manual new lesion masks can then be cleaned with `clean-roi-masks` before radiomics extraction.

## Radiomics Input Layout

Radiomics extraction expects images and ROI masks to be linked by the same case folder name. The folder name does not need to be a real patient ID; it only needs to match between images and ROIs.

```text
Images/
  case_001/
    image.nii.gz
  case_002/
    image.nii.gz

ROIs/
  Lesions/
    case_001/
      lesion_1.nii.gz
      lesion_2.nii.gz
    case_002/
      lesion_1.nii.gz

  Healthy/
    case_001/
      healthy_1.nii.gz
    case_002/
      healthy_1.nii.gz
```

The first folder level under `ROIs/` becomes the ROI label in the output table. For example, `Lesions`, `Healthy`, `NAWM`, or any custom folder name will be written to the `ROI_Label` column.

Each mask becomes one row in the output feature table. If a case has five lesion masks and five healthy masks, the result will contain ten rows for that case per discretization value.

Radiomics extraction uses the following feature classes by default:

```text
shape
firstorder
glcm
glrlm
glszm
gldm
ngtdm
```

Only the original image type is enabled. Images are not normalized or resampled inside PyRadiomics by default.

## Output Overview

Typical output:

```text
Output/
  Preprocessed_FLAIR/
  Difference_Images/
  Manual_Lesions/
  FLAMeS_Lesions/
    Existing_Pre/
    Post/
  Healthy/
  Cleaned_ROIs/
    Lesions/
    Healthy/
  Masks/
    White_Matter/
      Patient_ID/
        Pre/
        Post/
  Radiomics/
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

- The pipeline uses `config.yaml` by default.
- For local runs, either edit `config.yaml` with your own paths or pass a private ignored config file with `--config config.local.yaml`.
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

* van Griethuysen, J. J. M., Fedorov, A., Parmar, C., Hosny, A., Aucoin, N., Narayan, V., Beets-Tan, R. G. H., Fillion-Robin, J. C., Pieper, S., & Aerts, H. J. W. L. (2017). Computational radiomics system to decode the radiographic phenotype. *Cancer Research, 77*(21), e104-e107. https://doi.org/10.1158/0008-5472.CAN-17-0339

## License

This project is released under the MIT License. See `LICENSE` for details.

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
