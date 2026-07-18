# MRI Pipeline

MRI Pipeline is a command-line project for organizing and preprocessing brain MRI data, with the current focus on FLAIR images. It supports sequence organization, FLAIR preprocessing, histogram-based difference images between Pre/Post scans, transform reuse, and organization of normalized outputs.

The recommended entry point is:

```bash
python run_pipeline.py run --input "/path/to/input" --output "/path/to/output"
```

The user provides the input and output paths from the command line. The default folder names, preprocessing settings, timepoint names, sequence names, normalization methods, and difference-image settings are stored in `config.yaml`.

## Installation

Clone or download the repository, then open a terminal in the project folder:

```bash
cd /path/to/MRI_pipeline
```

Install the Python requirements:

```bash
pip install -r requirements.txt
```

Check the CLI:

```bash
python run_pipeline.py --help
```

For skull stripping, HD-BET must also be available from the terminal:

```bash
hd-bet --help
```

## Main CLI Pattern

Most workflows use:

```bash
python run_pipeline.py run --input "/path/to/input" --output "/path/to/output" --steps STEP_1 STEP_2
```

If `--steps` is not provided, the pipeline uses `run.default_steps` from `config.yaml`.

Example:

```bash
python run_pipeline.py run --input "/data/raw_mri" --output "/data/processed_mri"
```

All generated folders are created inside the selected `--output` folder.

## Project Structure

```text
MRI_pipeline/
  config.yaml
  run_pipeline.py
  requirements.txt
  README.md
  mri_pipeline/
    utils/
    organize/
    preprocessing/
    lesions/
    radiomics/
```

## Configuration

The current `config.yaml` is centered around the `run` section:

```yaml
run:
  default_steps:
    - split-sequences
    - preprocess-flair
    - split-normalizations

  folders:
    split_sequences: "By_Sequence"
    preprocessed_flair: "Preprocessed_FLAIR"
    difference_images: "Difference_Images"
    organized_pre: "Organized_Pre"
    organized_post: "Organized_Post"
    transforms: "Transforms"

  timepoints:
    pre: "Pre"
    post: "Post"
```

Folder names are relative to `--output`.

Example:

```bash
python run_pipeline.py run --input "/data/raw_mri" --output "/data/processed_mri"
```

creates outputs such as:

```text
/data/processed_mri/
  By_Sequence/
  Preprocessed_FLAIR/
  Difference_Images/
  Organized_Pre/
  Organized_Post/
  Transforms/
```

Before running registration, set the atlas/reference image path in `config.yaml`:

```yaml
run:
  preprocess_flair:
    atlas_path: "/path/to/reference_or_atlas_FLAIR.nii.gz"
```

## Supported Input Layouts

### Multiple Patients

```text
Input/
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
```

Run:

```bash
python run_pipeline.py run --input "/data/Input" --output "/data/Output"
```

### Single Patient Folder

You can pass one patient folder directly:

```text
Patient_001/
  Pre/
    Patient_001_FLAIR.nii.gz
  Post/
    Patient_001_FLAIR.nii.gz
```

Run:

```bash
python run_pipeline.py run --input "/data/Patient_001" --output "/data/Output"
```

### Pre-Only Folder

If no `Pre` or `Post` folders are found, the folder is treated as a Pre-only case:

```text
Patient_001/
  Patient_001_FLAIR.nii.gz
```

### Single FLAIR File

You can preprocess a single NIfTI file:

```bash
python run_pipeline.py run \
  --input "/data/Patient_001/Pre/Patient_001_FLAIR.nii.gz" \
  --output "/data/Output" \
  --steps preprocess-flair
```

If the file is inside a `Pre` or `Post` folder, the timepoint is inferred from the parent folder. Otherwise, the file is treated as `Pre`.

## Pipeline Steps

The `run` command supports:

```text
split-sequences
preprocess-flair
make-diff-images
split-normalizations
```

You can run one step:

```bash
python run_pipeline.py run --input "/data/Input" --output "/data/Output" --steps preprocess-flair
```

or several steps in order:

```bash
python run_pipeline.py run \
  --input "/data/Input" \
  --output "/data/Output" \
  --steps split-sequences preprocess-flair make-diff-images split-normalizations
```

## Step: split-sequences

This step organizes files by timepoint and sequence.

Example input:

```text
Input/
  Patient_001/
    Pre/
      scan_FLAIR.nii.gz
      scan_dDTI.nii.gz
    Post/
      scan_FLAIR.nii.gz
```

Command:

```bash
python run_pipeline.py run --input "/data/Input" --output "/data/Output" --steps split-sequences
```

Example output:

```text
Output/
  By_Sequence/
    Pre_FLAIR/
      Patient_001/
        scan_FLAIR.nii.gz
    Pre_dDTI/
      Patient_001/
        scan_dDTI.nii.gz
    Post_FLAIR/
      Patient_001/
        scan_FLAIR.nii.gz
```

Sequence names are configured in `config.yaml`:

```yaml
run:
  sequences:
    - FLAIR
    - dDTI
    - faDTI
    - isoDTI
```

## Step: preprocess-flair

This step preprocesses FLAIR images.

Available internal preprocessing steps:

```text
n4
registration
skull-strip
normalization
```

Default order in `config.yaml`:

```yaml
run:
  preprocess_flair:
    steps:
      - n4
      - registration
      - skull-strip
      - normalization
```

Step order matters. Each step receives the output of the previous step. `normalization` creates normalized variants and should be used as the final preprocessing step when combined with other preprocessing steps.

Run only the configured preprocessing:

```bash
python run_pipeline.py run --input "/data/Input" --output "/data/Output" --steps preprocess-flair
```

Override preprocessing steps from the command line:

```bash
python run_pipeline.py run \
  --input "/data/Input" \
  --output "/data/Output" \
  --steps preprocess-flair \
  --preprocess-steps n4 registration skull-strip normalization
```

Only registration for a single FLAIR image:

```bash
python run_pipeline.py run \
  --input "/data/Patient_001/Pre/Patient_001_FLAIR.nii.gz" \
  --output "/data/Output" \
  --steps preprocess-flair \
  --preprocess-steps registration
```

Registration and skull stripping for a single FLAIR image:

```bash
python run_pipeline.py run \
  --input "/data/Patient_001/Pre/Patient_001_FLAIR.nii.gz" \
  --output "/data/Output" \
  --steps preprocess-flair \
  --preprocess-steps registration skull-strip
```

Example output:

```text
Output/
  Preprocessed_FLAIR/
    Patient_001/
      Pre/
        Patient_001_FLAIR_R.nii
        Patient_001_FLAIR_R_brain.nii.gz
        Patient_001_FLAIR_R_brain_z-score.nii.gz
        Patient_001_FLAIR_R_brain_min-max.nii.gz
        Patient_001_FLAIR_R_brain_fcm.nii.gz
        Patient_001_FLAIR_R_brain_whitestripe.nii.gz
```

## Registration Transforms

Transforms are saved under the selected `--output` folder:

```text
Output/
  Transforms/
    Pre/
      Patient_001/
        Patient_001.tfm
    Post/
      Patient_001/
        Patient_001.tfm
```

The behavior is controlled by:

```yaml
run:
  transforms:
    save: true
    overwrite: false
    pre_folder: "Pre"
    post_folder: "Post"
```

Behavior:

```text
save: true
  New estimated transforms are saved.

overwrite: false
  If a patient transform already exists, it is reused.
  If no transform exists, a new one is estimated.

overwrite: true
  Existing transforms are ignored and new transforms are estimated.
```

## Step: make-diff-images

This step creates histogram-matched absolute difference images between Post and Pre FLAIR images.

The difference image logic is:

```text
1. Use Pre as the reference image.
2. Use Post as the source image.
3. If needed, register source to reference.
4. Histogram-match source to reference.
5. Save the absolute difference image.
```

The histogram settings come from `config.yaml`:

```yaml
run:
  difference_images:
    source_timepoint: "Post"
    reference_timepoint: "Pre"
    histogram_levels: 256
    match_points: 10
    threshold_at_mean: true
```

### Difference Images Inside the Pipeline

If `make-diff-images` runs after `preprocess-flair` in the same command, it uses:

```text
Output/Preprocessed_FLAIR/
```

as the source folder.

Example:

```bash
python run_pipeline.py run \
  --input "/data/Input" \
  --output "/data/Output" \
  --steps preprocess-flair make-diff-images \
  --preprocess-steps registration skull-strip
```

If `make-diff-images` runs by itself through `run`, it uses `--input` as the source folder.

Example with an already preprocessed folder:

```bash
python run_pipeline.py run \
  --input "/data/Already_Preprocessed_FLAIR" \
  --output "/data/Output" \
  --steps make-diff-images
```

Expected folder layout:

```text
Already_Preprocessed_FLAIR/
  Patient_001/
    Pre/
      Patient_001_FLAIR_R_brain.nii.gz
    Post/
      Patient_001_FLAIR_R_brain.nii.gz
```

The pipeline first looks for skull-stripped registered images:

```text
*_R_brain.nii*
```

If those do not exist, it looks for registered images:

```text
*_R.nii*
```

By default, pipeline folder mode does not register missing pairs automatically. If you want it to register missing pairs before creating difference images, add:

```bash
--diff-register-missing
```

Example:

```bash
python run_pipeline.py run \
  --input "/data/Already_Preprocessed_FLAIR" \
  --output "/data/Output" \
  --steps make-diff-images \
  --diff-register-missing
```

Difference image output:

```text
Output/
  Difference_Images/
    Patient_001/
      Pair_YYYYMMDD_HHMMSS/
        reference.nii.gz
        source_registered.nii.gz
        difference.nii.gz
        source_to_reference.tfm
```

If registration was not needed, `source_to_reference.tfm` may not be created.

### Standalone Difference Image From Two Files

You can create a difference image directly from two NIfTI files without running the full pipeline:

```bash
python run_pipeline.py make-diff-images \
  --reference "/data/Patient_001/Pre/Patient_001_Pre_FLAIR.nii.gz" \
  --source "/data/Patient_001/Post/Patient_001_Post_FLAIR.nii.gz" \
  --output "/data/Difference_Output"
```

Standalone mode checks whether the two images have the same geometry. If they do not, the source image is registered to the reference image automatically.

Output:

```text
Difference_Output/
  Pair_YYYYMMDD_HHMMSS/
    reference.nii.gz
    source_registered.nii.gz
    difference.nii.gz
    source_to_reference.tfm
```

## Step: split-normalizations

This step organizes final brain images and normalized images into separate Pre and Post output roots.

If it runs after `preprocess-flair` in the same command, it uses:

```text
Output/Preprocessed_FLAIR/
```

as its source. If it runs by itself, it uses `--input`.

Command:

```bash
python run_pipeline.py run \
  --input "/data/Already_Preprocessed_FLAIR" \
  --output "/data/Output" \
  --steps split-normalizations
```

Example input:

```text
Already_Preprocessed_FLAIR/
  Patient_001/
    Pre/
      scan_R_brain.nii.gz
      scan_R_brain_z-score.nii.gz
      scan_R_brain_min-max.nii.gz
    Post/
      scan_R_brain.nii.gz
      scan_R_brain_fcm.nii.gz
```

Example output:

```text
Output/
  Organized_Pre/
    Pre/
      Patient_001/
        scan_R_brain.nii.gz
    z-score/
      Patient_001/
        scan_R_brain_z-score.nii.gz
    min-max/
      Patient_001/
        scan_R_brain_min-max.nii.gz

  Organized_Post/
    Post/
      Patient_001/
        scan_R_brain.nii.gz
    fcm/
      Patient_001/
        scan_R_brain_fcm.nii.gz
```

Configured normalization names:

```yaml
run:
  normalizations:
    - z-score
    - min-max
    - fcm
    - whitestripe
```

The non-normalized final image is detected when the filename ends with:

```text
_brain.nii
_brain.nii.gz
```

## Common Workflows

### Full FLAIR Workflow

```bash
python run_pipeline.py run \
  --input "/data/Input" \
  --output "/data/Output" \
  --steps split-sequences preprocess-flair make-diff-images split-normalizations \
  --preprocess-steps n4 registration skull-strip normalization
```

### Add a New Patient to Existing Output Folders

Use the same output root as before:

```bash
python run_pipeline.py run \
  --input "/data/NewPatient_001" \
  --output "/data/Output" \
  --steps preprocess-flair make-diff-images split-normalizations
```

This writes the new patient into the same output structure:

```text
Output/
  Preprocessed_FLAIR/
  Difference_Images/
  Organized_Pre/
  Organized_Post/
  Transforms/
```

### Only Organize New Files by Sequence

```bash
python run_pipeline.py run \
  --input "/data/NewRawFiles" \
  --output "/data/Output" \
  --steps split-sequences
```

### Only Organize Already Normalized Files

```bash
python run_pipeline.py run \
  --input "/data/Already_Preprocessed_FLAIR" \
  --output "/data/Output" \
  --steps split-normalizations
```

## Copy vs Move

Organization steps copy files by default.

To move files instead of copying them:

```bash
python run_pipeline.py run \
  --input "/data/Input" \
  --output "/data/Output" \
  --steps split-sequences \
  --move
```

Use `--move` carefully because it modifies the input location.

## Progress Output

The pipeline uses `tqdm` progress bars for long-running operations such as:

```text
run steps
patient loops
preprocessing steps
normalization methods
```

HD-BET and nnU-Net may also print their own progress messages and citation text during skull stripping. Those messages come from external tools.

## Troubleshooting

### No Files Were Created

Check that:

```text
1. --input exists.
2. The input contains .nii or .nii.gz files.
3. Filenames contain the configured sequence or normalization names.
4. The expected Pre/Post folder names match config.yaml.
```

### Registration Uses an Old Transform

If this exists:

```text
Output/Transforms/Pre/Patient_001/Patient_001.tfm
```

and:

```yaml
overwrite: false
```

the transform is reused. Set:

```yaml
overwrite: true
```

to force a new registration transform.

### make-diff-images Skips a Patient

Folder mode expects each patient to contain both timepoints:

```text
Patient_001/
  Pre/
  Post/
```

and registered images such as:

```text
*_R_brain.nii*
```

or:

```text
*_R.nii*
```

If registered images are missing and you want the diff step to register them automatically, add:

```bash
--diff-register-missing
```

### HD-BET Output Is Very Verbose

HD-BET prints citation information, nnU-Net environment warnings, prediction progress, and export messages. This is expected when skull stripping is running.

### Recommended Output Path

Use a dedicated output folder:

```bash
python run_pipeline.py run --input "/data/Input" --output "/data/Output"
```

Avoid writing directly to a broad location such as a desktop or home folder, because the pipeline creates several subfolders.

## Notes for Future Development

Planned project areas include:

```text
lesion segmentation management
radiomics feature extraction
brain MRI radiomics tables
```

The `lesions/` and `radiomics/` modules are present so these workflows can be added cleanly later.
