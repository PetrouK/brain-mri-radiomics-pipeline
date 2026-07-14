# MRI Pipeline

This project organizes and runs basic MRI preprocessing workflows, with the main focus on FLAIR images. The user provides an input path and an output path from the command line. The `config.yaml` file defines output folder names, preprocessing steps, timepoint names, sequences, normalization methods, and transform behavior.

## Quick Start

Open a terminal inside the project folder:

```bash
cd /path/to/MRI_pipeline
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Show available options:

```bash
python run_pipeline.py --help
```

Run the default workflow:

```bash
python run_pipeline.py run --input "/path/to/input" --output "/path/to/output"
```

If `--steps` is not provided, the pipeline uses `run.default_steps` from `config.yaml`.

## Main Concept

The user provides:

```text
--input   the input folder or input file to process
--output  the root folder where all results will be written
```

All outputs are created under `--output`:

```text
OUTPUT/
  By_Sequence/
  Preprocessed_FLAIR/
  Organized_Pre/
  Organized_Post/
  Transforms/
```

These folder names are configured in `config.yaml`.

## Project Structure

```text
MRI_pipeline/
  config.yaml
  run_pipeline.py
  requirements.txt
  README.md
  README_EN.md
  mri_pipeline/
    utils/
    organize/
    preprocessing/
    lesions/
    radiomics/
```

## config.yaml

The current configuration is centered under the `run` section.

```yaml
run:
  default_steps:
    - split-sequences
    - preprocess-flair
    - split-normalizations

  folders:
    split_sequences: "By_Sequence"
    preprocessed_flair: "Preprocessed_FLAIR"
    organized_pre: "Organized_Pre"
    organized_post: "Organized_Post"
    transforms: "Transforms"
```

The `folders` values are relative to the selected `--output`.

Example:

```bash
python run_pipeline.py run --input "/path/to/new_data" --output "/path/to/study_output"
```

writes to:

```text
/path/to/study_output/By_Sequence/
/path/to/study_output/Preprocessed_FLAIR/
/path/to/study_output/Organized_Pre/
/path/to/study_output/Organized_Post/
/path/to/study_output/Transforms/
```

## Supported Input Layouts

### Multiple patients with Pre/Post

```text
Input/
  Patient_001/
    Pre/
      Patient_001_FLAIR.nii
    Post/
      Patient_001_FLAIR.nii
  Patient_002/
    Pre/
      Patient_002_FLAIR.nii.gz
```

### A single patient with Pre/Post

You can provide the patient folder directly:

```text
Patient_001/
  Pre/
    Patient_001_FLAIR.nii
  Post/
    Patient_001_FLAIR.nii
```

```bash
python run_pipeline.py run --input "/path/to/new_data/Patient_001" --output "/path/to/output"
```

### Pre-only patient without Pre/Post folders

If `Pre` and `Post` folders do not exist, the folder is treated as `Pre`.

```text
Patient_001/
  Patient_001_FLAIR.nii
```

### Single FLAIR file

You can provide a single NIfTI file directly:

```bash
python run_pipeline.py run --input "/path/to/new_data/Patient_001/Pre/Patient_001_FLAIR.nii" --output "/path/to/output" --steps preprocess-flair
```

If the file is inside a `Pre` or `Post` folder, the timepoint is inferred from the parent folder. Otherwise, it is treated as `Pre`.

## Run Steps

The `run` command supports three pipeline steps:

```text
split-sequences
preprocess-flair
split-normalizations
```

### split-sequences

Organizes raw files by timepoint and sequence.

Input:

```text
Input/
  Patient_001/
    Pre/
      scan_FLAIR.nii
      scan_dDTI.nii
    Post/
      scan_FLAIR.nii
```

Output:

```text
OUTPUT/By_Sequence/
  Pre_FLAIR/
    Patient_001/
  Pre_dDTI/
    Patient_001/
  Post_FLAIR/
    Patient_001/
```

Sequences are configured in `config.yaml`:

```yaml
sequences:
  - FLAIR
  - dDTI
  - faDTI
  - isoDTI
```

### preprocess-flair

Runs preprocessing only for FLAIR images.

Available internal preprocessing steps:

```text
n4
registration
skull-strip
normalization
```

The default order is configured in `config.yaml`:

```yaml
preprocess_flair:
  steps:
    - n4
    - registration
    - skull-strip
    - normalization
```

Step order matters. Each step receives the output of the previous step, except `normalization`, which creates normalized output variants but does not replace the main processing image. Therefore, when `normalization` is used together with other steps, it must be the final preprocessing step.

Output:

```text
OUTPUT/Preprocessed_FLAIR/
  Patient_001/
    Pre/
      scan_corr.nii
      scan_corr_R.nii
      scan_corr_R_brain.nii.gz
      scan_corr_R_brain_z-score.nii.gz
      scan_corr_R_brain_min-max.nii.gz
      scan_corr_R_brain_fcm.nii.gz
      scan_corr_R_brain_whitestripe.nii.gz
    Post/
      ...
```

### split-normalizations

Organizes final brain images and normalized images into separate Pre and Post roots.

Output:

```text
OUTPUT/Organized_Pre/
  Pre/
    Patient_001/
      scan_corr_R_brain.nii.gz
  z-score/
    Patient_001/
      scan_corr_R_brain_z-score.nii.gz
  min-max/
  fcm/
  whitestripe/

OUTPUT/Organized_Post/
  Post/
    Patient_001/
      scan_corr_R_brain.nii.gz
  z-score/
  min-max/
  fcm/
  whitestripe/
```

If `split-normalizations` runs after `preprocess-flair` in the same command, it uses:

```text
OUTPUT/Preprocessed_FLAIR/
```

as its source. If it runs by itself, it uses `--input` as its source.

## Command Examples

### Full workflow

```bash
python run_pipeline.py run --input "/path/to/new_data" --output "/path/to/output"
```

This is equivalent to:

```bash
python run_pipeline.py run --input "/path/to/new_data" --output "/path/to/output" --steps split-sequences preprocess-flair split-normalizations
```

### Only organize by sequence

```bash
python run_pipeline.py run --input "/path/to/new_data" --output "/path/to/output" --steps split-sequences
```

### Only FLAIR preprocessing

```bash
python run_pipeline.py run --input "/path/to/new_data" --output "/path/to/output" --steps preprocess-flair
```

### Only registration for one FLAIR file

```bash
python run_pipeline.py run --input "/path/to/new_data/Patient_001/Pre/Patient_001_FLAIR.nii" --output "/path/to/output" --steps preprocess-flair --preprocess-steps registration
```

Output:

```text
/path/to/output/
  Preprocessed_FLAIR/
    Patient_001/
      Pre/
        Patient_001_FLAIR_R.nii
  Transforms/
    Pre/
      Patient_001/
        Patient_001.tfm
```

### Registration and skull stripping for one file

```bash
python run_pipeline.py run --input "/path/to/new_data/Patient_001/Pre/Patient_001_FLAIR.nii" --output "/path/to/output" --steps preprocess-flair --preprocess-steps registration skull-strip
```

### N4, registration, skull stripping, normalization

```bash
python run_pipeline.py run --input "/path/to/new_data" --output "/path/to/output" --steps preprocess-flair --preprocess-steps n4 registration skull-strip normalization
```

### Organize already preprocessed / normalized files

If you already have:

```text
Ready/
  Patient_001/
    Pre/
      scan_corr_R_brain.nii.gz
      scan_corr_R_brain_z-score.nii.gz
    Post/
      scan_corr_R_brain.nii.gz
      scan_corr_R_brain_min-max.nii.gz
```

run:

```bash
python run_pipeline.py run --input "/path/to/ready_data" --output "/path/to/output" --steps split-normalizations
```

## Transforms and Registration

Transforms are output-relative:

```text
OUTPUT/Transforms/
  Pre/
    Patient_ID/
      Patient_ID.tfm
  Post/
    Patient_ID/
      Patient_ID.tfm
```

In `config.yaml`:

```yaml
transforms:
  save: true
  overwrite: false
```

Behavior:

```text
save: true
  if a new transform is estimated, it is saved.

overwrite: false
  if a .tfm already exists for the patient, it is reused.
  if no .tfm exists, registration is estimated.

overwrite: true
  any existing .tfm is ignored and a new transform is estimated.
```

## Normalization Methods

Supported methods:

```text
z-score
min-max
fcm
whitestripe
```

`split-normalizations` detects normalized files from their filenames. Examples:

```text
scan_corr_R_brain_z-score.nii.gz
scan_corr_R_brain_min-max.nii.gz
scan_corr_R_brain_fcm.nii.gz
scan_corr_R_brain_whitestripe.nii.gz
```

The non-normalized final image is placed under `Pre/` or `Post/` when the filename ends with:

```text
_brain.nii
_brain.nii.gz
```

## Copy or Move

By default, organization steps copy files.

To move instead:

```bash
python run_pipeline.py run --input "/path/to/new_data" --output "/path/to/output" --steps split-sequences --move
```

Warning: `--move` moves files in organization steps. Use it only when you are sure.

## Progress and Terminal Output

The pipeline uses `tqdm` progress bars for:

```text
run steps
patients
preprocessing steps
normalization methods
```

HD-BET/nnU-Net also prints its own messages, including citation text and prediction progress. These messages come from the external HD-BET tool.

## Dependencies

Main Python packages:

```text
PyYAML
numpy
scipy
nibabel
SimpleITK
torch
HD-BET
pyradiomics
pandas
openpyxl
tqdm
```

For skull stripping, this command must work:

```bash
hd-bet --help
```

Docker is required for SynthSeg-related commands if those workflows are used separately.

## Troubleshooting

### Nothing was created

Check that `--input` is correct and contains `.nii` or `.nii.gz` files. If you provide a single file, it must be a NIfTI file.

### Registration reuses an old transform

If this exists:

```text
OUTPUT/Transforms/Pre/Patient_ID/Patient_ID.tfm
```

and the config has:

```yaml
overwrite: false
```

the pipeline will reuse it. To force new registration, set:

```yaml
overwrite: true
```

### HD-BET prints many warnings

Warnings about `nnUNet_raw`, `nnUNet_preprocessed`, and `nnUNet_results` come from HD-BET/nnU-Net. If prediction finishes and you see `done with ...`, skull stripping completed.

### Do not write directly to Desktop

Prefer:

```bash
--output "/path/to/output"
```

instead of:

```bash
--output "/path/to"
```

so the Desktop does not fill up with pipeline folders.

