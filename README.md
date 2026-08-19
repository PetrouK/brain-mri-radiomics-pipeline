# Brain MRI Radiomics Pipeline

Command-line pipeline for longitudinal brain MRI preprocessing, lesion/white matter mask preparation, ROI cleaning, and radiomics extraction.

The project supports research workflows where **Post/follow-up lesions are manually segmented** and compared with corresponding Pre/baseline MRI data. Manual Post lesion masks should preferably be drawn on the registered Post image so that Pre, Post, white matter masks, lesion masks, healthy mirrored ROIs, and radiomics features are in the same image space.

Research use only. This is not a clinical diagnostic tool. The workflow has been tested on brain MRI data acquired on a 3 Tesla MRI system.

## Features

- Organize MRI files by sequence and timepoint.
- Preprocess FLAIR images with N4, registration, skull stripping, and normalization.
- Save and reuse registration transforms.
- Create histogram-matched Pre/Post difference images.
- Generate white matter, CSF, and ventricular masks with SynthSeg.
- Generate lesion masks with FLAMeS.
- Mirror manual lesion ROIs to create healthy control ROIs.
- Clean lesion and healthy ROIs using white matter and exclusion masks.
- Extract PyRadiomics features with `binWidth` or `binCount`.

## Installation

```bash
git clone https://github.com/PetrouK/brain-mri-radiomics-pipeline.git
cd brain-mri-radiomics-pipeline
pip install -r requirements.txt
python run_pipeline.py --help
```

External tools are required for some steps and are not redistributed here:

- HD-BET for skull stripping.
- FLAMeS / nnU-Net v2 for lesion segmentation.
- SynthSeg for anatomical segmentation / white matter masks.

Configure local paths in `config.yaml` or in a private ignored file such as `config.local.yaml`.

## Radiomics Environment

PyRadiomics is best installed in a separate environment to avoid conflicts with deep learning dependencies.

```bash
conda create -n radiomics_env python=3.10 -y
conda activate radiomics_env
pip install -r requirements-radiomics.txt
```

Run only radiomics commands from this environment.

## Input Layout

Recommended longitudinal input:

```text
Input/
  Patients/
    Patient_ID/
      Pre/
        pre_flair.nii.gz
      Post/
        post_flair.nii.gz
  Transforms/
    Pre/
      Patient_ID/
        optional_pre_transform.tfm
    Post/
      Patient_ID/
        optional_post_transform.tfm
```

If transforms are missing, registration is computed and saved under the output folder.

## Output Layout

```text
Output/
  By_Sequence/
  Preprocessed_FLAIR/
  Difference_Images/
  Organized_Pre/
  Organized_Post/
  Transforms/

  Lesions/
    Patient_ID/
      manual_post_lesion_masks.nii.gz

  FLAMeS_Lesions/
    Existing_Pre/
      Patient_ID/
    Post/
      Patient_ID/

  Masks/
    White_Matter/
      Patient_ID/
        Pre/
        Post/
    CSF/
      Patient_ID/
        Pre/
        Post/
    Ventricles/
      Patient_ID/
        Pre/
        Post/

  Healthy/
    Patient_ID/

  Cleaned_ROIs/
    Lesions/
      Patient_ID/
    Healthy/
      Patient_ID/

  Radiomics/
```

`Lesions/` is for manually segmented Post/new lesions. `FLAMeS_Lesions/` is reserved for FLAMeS outputs.

## Common Commands

Run preprocessing, difference images, and organization:

```bash
python run_pipeline.py run --config "config.local.yaml" --input "/data/Input" --output "/data/Output" --steps split-sequences preprocess-flair make-diff-images split-normalizations --preprocess-steps n4 registration skull-strip diff normalization
```

Generate SynthSeg masks:

```bash
python run_pipeline.py segment-white-matter --config "config.local.yaml" --input "/data/Output/Preprocessed_FLAIR" --output "/data/Output" --registered-only
python run_pipeline.py segment-csf --config "config.local.yaml" --input "/data/Output/Preprocessed_FLAIR" --output "/data/Output" --registered-only
python run_pipeline.py segment-ventricles --config "config.local.yaml" --input "/data/Output/Preprocessed_FLAIR" --output "/data/Output" --registered-only
```

Organize normalized outputs without overwriting existing files:

```bash
python run_pipeline.py split-normalizations --config "config.local.yaml" --input "/data/Output/Preprocessed_FLAIR" --output "/data/Output"
```

Generate FLAMeS masks:

```bash
python run_pipeline.py segment-lesions --config "config.local.yaml" --input "/data/Output/Organized_Pre/Pre" --output "/data/Output" --lesion-folder Existing_Pre
python run_pipeline.py segment-lesions --config "config.local.yaml" --input "/data/Output/Organized_Post/Post" --output "/data/Output" --lesion-folder Post
```

Mirror manual lesion masks to healthy control ROIs:

```bash
python run_pipeline.py mirror-roi-masks --input "/data/Output/Lesions" --output "/data/Output/Healthy"
```

The mirror step renames `Segmentation` to `Healthy`, for example:

```text
Patient_ID_Segmentation_1.nii -> Patient_ID_Healthy_1.nii
```

Clean manual lesion ROIs inside white matter and away from existing Pre lesions:

```bash
python run_pipeline.py clean-roi-masks --roi-root "/data/Output/Lesions" --allowed-root "/data/Output/Masks/White_Matter" --allowed-timepoint Post --exclusion-root "/data/Output/FLAMeS_Lesions/Existing_Pre" --output "/data/Output/Cleaned_ROIs/Lesions"
```

Clean manual lesion ROIs inside white matter, outside CSF/ventricles, and away from existing Pre lesions:

```bash
python run_pipeline.py clean-roi-masks --roi-root "/data/Output/Lesions" --allowed-root "/data/Output/Masks/White_Matter" --allowed-timepoint Post --forbidden-root "/data/Output/Masks/CSF" "/data/Output/Masks/Ventricles" --forbidden-timepoint Post --exclusion-root "/data/Output/FLAMeS_Lesions/Existing_Pre" --output "/data/Output/Cleaned_ROIs/Lesions"
```

Clean manual lesion ROIs outside CSF/ventricles and away from existing Pre lesions, without requiring white matter:

```bash
python run_pipeline.py clean-roi-masks --roi-root "/data/Output/Lesions" --forbidden-root "/data/Output/Masks/CSF" "/data/Output/Masks/Ventricles" --forbidden-timepoint Post --exclusion-root "/data/Output/FLAMeS_Lesions/Existing_Pre" --output "/data/Output/Cleaned_ROIs/Lesions"
```

Clean healthy ROIs:

```bash
python run_pipeline.py clean-roi-masks --roi-root "/data/Output/Healthy" --allowed-root "/data/Output/Masks/White_Matter" --allowed-timepoint Post --exclusion-root "/data/Output/FLAMeS_Lesions/Existing_Pre" --output "/data/Output/Cleaned_ROIs/Healthy"
```

Use `--exclusion-dilation 0` to remove only overlapping voxels. Use `--exclusion-dilation 1` to also remove voxels touching the exclusion mask.

By default, existing outputs are skipped. Add `--overwrite-existing` only when outputs should be regenerated.

## Radiomics

Radiomics extraction expects image and ROI case folder names to match.

```text
Images/
  case_001/
    image.nii.gz

ROIs/
  Lesions/
    case_001/
      lesion_1.nii.gz
  Healthy/
    case_001/
      healthy_1.nii.gz
```

The first folder level under `ROIs/` becomes the `ROI_Label`. Each mask becomes one row per discretization value.

```bash
python run_pipeline.py extract-radiomics --image-root "/data/Images" --roi-root "/data/ROIs" --output "/data/Radiomics" --discretization-mode binCount --discretization-values 32 64 128 --max-workers 8
```

Direct `binWidth` values:

```bash
python run_pipeline.py extract-radiomics --image-root "/data/Images" --roi-root "/data/ROIs" --output "/data/Radiomics" --discretization-mode binWidth --discretization-values 5 10 20 --max-workers 8
```

Target bin counts converted to `binWidth`:

```bash
python run_pipeline.py extract-radiomics --image-root "/data/Images" --roi-root "/data/ROIs" --output "/data/Radiomics" --discretization-mode binWidth --discretization-values 32 64 128 --values-are-target-bins --max-workers 8
```

## Notes

- Keep personal paths in `config.local.yaml`; do not commit that file.
- Do not commit NIfTI images, transforms, model files, or external tool repositories.
- `tools/` can be used locally for FLAMeS or SynthSeg and should remain ignored by Git.

## References

* Isensee, F., Schell, M., Tursunova, I., Brugnara, G., Bonekamp, D., Neuberger, U., Wick, A., Schlemmer, H. P., Heiland, S., Wick, W., Bendszus, M., Maier-Hein, K. H., & Kickingereder, P. (2019). Automated brain extraction of multisequence MRI using artificial neural networks. *Human Brain Mapping, 40*(17), 4952-4964. https://doi.org/10.1002/hbm.24750

* Billot, B., Greve, D. N., Puonti, O., Thielscher, A., Van Leemput, K., Fischl, B., Dalca, A. V., & Iglesias, J. E. (2023). SynthSeg: Segmentation of brain MRI scans of any contrast and resolution without retraining. *Medical Image Analysis, 86*, 102789. https://doi.org/10.1016/j.media.2023.102789

* Dereskewicz, E., La Rosa, F., Dos Santos Silva, J., et al. (2025). A novel convolutional neural network for automated multiple sclerosis brain lesion segmentation. *Journal of Neuroimaging, 35*(5), e70085. https://doi.org/10.1111/jon.70085

* Isensee, F., Jaeger, P. F., Kohl, S. A. A., Petersen, J., & Maier-Hein, K. H. (2021). nnU-Net: A self-configuring method for deep learning-based biomedical image segmentation. *Nature Methods, 18*(2), 203-211. https://doi.org/10.1038/s41592-020-01008-z

* van Griethuysen, J. J. M., Fedorov, A., Parmar, C., Hosny, A., Aucoin, N., Narayan, V., Beets-Tan, R. G. H., Fillion-Robin, J. C., Pieper, S., & Aerts, H. J. W. L. (2017). Computational radiomics system to decode the radiographic phenotype. *Cancer Research, 77*(21), e104-e107. https://doi.org/10.1158/0008-5472.CAN-17-0339

## License

Released under the MIT License. See `LICENSE` for details.
