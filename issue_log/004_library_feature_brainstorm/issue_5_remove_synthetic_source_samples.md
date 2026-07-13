# Issue #5 Remove Synthetic Source Samples

## 依頼

ユーザーは「自作側の samplefile は削除してください」と依頼した。

## 実施内容

自作側の synthetic fixture を削除した。

削除したもの:

- `main_artifact/fixtures/demo_programming_tech_library/source_samples/html/requirements_engineering_overview.html`
- `main_artifact/fixtures/demo_programming_tech_library/source_samples/pdf/software_design_principles.pdf`
- `main_artifact/fixtures/demo_programming_tech_library/source_samples/image/software_quality_practices.png`
- `main_artifact/fixtures/demo_programming_tech_library/records/alpha_source_samples.json`

残したもの:

- `main_artifact/fixtures/demo_programming_tech_library/source_samples/actual/`
- `main_artifact/fixtures/demo_programming_tech_library/records/actual_web_source_samples.json`

## 判断

- 今後の extractor / importer / preview 検証では actual source sample を使う。
- synthetic fixture の作成経緯は issue log に履歴として残すが、現行 sample set としては扱わない。
