# Awesome Machine Learning in Epigenetics [![Awesome](https://awesome.re/badge.svg)](https://awesome.re)

A curated list of "awesome" machine learning resources, datasets, and papers in epigenetics research. This collection aims to bridge the gap between machine learning and epigenetics, providing valuable references for researchers and practitioners.

## Contents

- [Papers](#papers)
  - [DNA Methylation](#dna-methylation)
  - [Histone Modifications](#histone-modifications)
  - [Chromatin Accessibility](#chromatin-accessibility)
  - [Multi-omics Integration](#multi-omics-integration)
  - [Liquid Biopsy](#liquid-biopsy)
  - [Novel Epigenetic Assays](#novel-epigenetic-assays)

- [Datasets](#datasets)
- [Contributing](#contributing)

## Papers

### DNA Methylation
<!-- AUTO-PAPERS:DNA_METHYLATION START -->
- [CpGene: a web application for epigenetic signature identification from DNA methylation arrays](https://doi.org/10.1093/bioinformatics/btag141) (2026) - AI-based feature ranking using scikit-learn for biomarker discovery in DNA methylation analysis, facilitating the identification of clinically relevant CpG sites.
- [DeepStrataAge: an interpretable deep-learning clock that reveals stage- and sex-divergent DNA methylation aging dynamics](https://doi.org/10.1038/s41514-026-00358-w) (2026) - Deep neural network (DNN) model for DNA methylation aging prediction achieving a mean absolute error of 1.
- [Epigenetic Biomarkers for Age Estimation in Forensic Samples: A CpG-Site-Specific DNA Methylation Approach Using Machine Learning for Biological Age Prediction](https://doi.org/10.66838/fy9w6842) (2026) - Random forest regression model for biological age prediction using DNA methylation at six CpG loci, achieving MAE of 2.
- [Integrative multi-cohort analysis of DNA methylation profiles for pancreatic ductal adenocarcinoma biomarker discovery and prognosis](https://doi.org/10.3389/fbinf.2026.1808516) (2026) - Interpretable machine-learning models for identifying a compact 18-CpG signature in pancreatic ductal adenocarcinoma, achieving reproducibility across four independent cohorts.
- [Methylation-Aware Embedding Geometry Emerges from Bisulfite Pretraining in DNA Language Models](https://openreview.net/forum?id=C4lGPSE0X7) (2026) - Continual pretraining of DNABERT2 on bisulfite sequencing reads reveals that methylation is encoded in representation space, shown via geometric diagnostics of embedding norms and cosine distances.
- [Multi-output learning for systematic missing value imputation in DNA methylation arrays.](https://doi.org/10.1093/bioadv/vbag052) (2026) - Multi-output regression and learning (MOREL) framework using support vector regression, random forest, and deep neural networks for systematic missing value imputation in DNA methylation arrays, achieving improved accuracy in epigenetic age prediction models.
<!-- AUTO-PAPERS:DNA_METHYLATION END -->

- [Epigenomic language models powered by Cerebras](https://arxiv.org/abs/2112.07571) (2021) - BERT model pretrained on human genome and across 127 cell types with DNA sequence and paired epigenetic state inputs. 
- [MethylNet: Deep learning for DNA methylation analysis](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-020-3443-8) (2020) - VAE for analyzing DNA methylation data.
- [DeepCpG: Accurate prediction of single-cell DNA methylation states using deep learning](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-017-1189-z) (2017) - CNN model for predicting single-cell DNA methylation states.
- [Detection of significantly differentially methylated regions in targeted bisulfite sequencing data](https://academic.oup.com/bioinformatics/article/29/13/1647/200453) (2013) - Stats model for identifying differentially methylated region (DMR) from microarray data (i.e. clustering/segment).
- [A nonparametric Bayesian approach for clustering bisulfate-based DNA methylation profiles](https://link.springer.com/article/10.1186/1471-2164-13-S6-S20) (2012) - Bayesian stats model for clustering/segment microarray data. 

### Histone Modifications
<!-- AUTO-PAPERS:HISTONE_MODIFICATIONS START -->
- [Machine and Deep Learning Reveal Sequence Determinants Encoding Bivalent Histone Modifications](https://doi.org/10.1038/s42003-026-09962-8) (2026) - XGBoost classifier with SHAP feature attribution for distinguishing bivalent from monovalent histone modifications based on k-mer sequence features, achieving high predictive accuracy.
- [PATTY corrects open-chromatin bias for improved bulk and single-cell CUT&Tag profiling.](https://doi.org/10.1038/s41467-026-73599-8) (2026) - Machine learning-based bias correction method PATTY for CUT&Tag profiling, enhancing histone modification signal detection and single-cell clustering accuracy.
<!-- AUTO-PAPERS:HISTONE_MODIFICATIONS END -->

- [DeepHistone: A deep learning approach to predicting histone modifications](https://bmcgenomics.biomedcentral.com/articles/10.1186/s12864-019-5489-4) (2019) - CNN-based model for histone modification prediction.
- [DeepDiff: DEEP-learning for predicting DIFFerential gene expression from histone modifications](https://academic.oup.com/bioinformatics/article/34/17/i891/5093224) (2018) - Hybrid (attention + LSTM) deep learning model for gene expression prediction from histone modification.

### Chromatin Accessibility
<!-- AUTO-PAPERS:CHROMATIN_ACCESSIBILITY START -->
- [Cross-species prediction reveals chromatin regions with increased accessibility in humans](https://doi.org/10.1126/sciadv.ady9169) (2026) - CNN-based model for cross-species prediction of chromatin accessibility, identifying 23,414 human predicted increased chromatin accessibility regions (hPICAs) across 111 cell types.
- [Evaluating single-cell ATAC-seq atlasing technologies using sequence-to-function modeling.](https://doi.org/10.1038/s41586-023-06819-6) (2026) - Random forest model for predicting candidate cis-regulatory elements based on sequence data, achieving high predictive accuracy across mammalian species.
<!-- AUTO-PAPERS:CHROMATIN_ACCESSIBILITY END -->

- [Effective gene expression prediction from sequence by integrating long-range interactions](https://www.nature.com/articles/s41592-021-01252-x) (2021) - Transformer-based model for chromatin accessibility prediction.
- [DeepTACT: predicting 3D chromatin contacts via bootstrapping deep learning](https://academic.oup.com/nar/article/47/10/e60/5380496) (2019) - A bootstrapping deep learning model to predict chromatin contacts between regulatory elements.
- [cisTopic: cis-regulatory topic modeling on single-cell ATAC-seq data](https://www.nature.com/articles/s41592-019-0367-1) (2019) - A probabilistic framework used to simultaneously discover coaccessible enhancers and stable cell states from sparse single-cell epigenomics data.

### Multi-omics Integration
<!-- AUTO-PAPERS:MULTI_OMICS START -->
- [Benchmarking component choices for unpaired single cell RNA and epigenomic integration](https://doi.org/10.1186/s13059-026-04071-5) (2026) - Neural network-based integration methods for unpaired single-cell RNA and epigenomic data, achieving improved clustering performance and cross-modality agreement.
- [Defining neurovascular ecosystem states with single-cell multi-omics and machine learning: insights into cerebrovascular remodeling in the tumor context](https://doi.org/10.3389/fcell.2026.1846929) (2026) - Interpretable machine learning framework for analyzing single-cell multi-omics data to define neurovascular ecosystem states in gliomas, revealing stable epigenetic foundations and regulatory dependencies.
<!-- AUTO-PAPERS:MULTI_OMICS END -->

- [SCENIC+: single-cell multiomic inference of enhancers and gene regulatory networks](https://www.nature.com/articles/s41592-023-01938-4) (2021) - Gradient-boost regression model for single-cell multiomic inference of enhancers and gene regulatory networks. 
- [MOFA+: A probabilistic framework for comprehensive integration of structured single-cell data](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-020-02015-1) (2020) - Framework for integrating multiple omics data types.

### Liquid Biopsy
<!-- AUTO-PAPERS:LIQUID_BIOPSY START -->
- [cfDECOR: a novel approach for estimating cell type contributions to cfDNA based on chromatin accessibility patterns](https://doi.org/10.1038/s41598-026-50180-3) (2026) - cfDECOR deconvolution model for predicting cell type contributions to cfDNA based on chromatin accessibility patterns, enhancing disease detection sensitivity.
- [Epigenetic Instability-Based Metrics in Cell-Free DNA for Early Cancer Detection.](https://doi.org/10.1158/1078-0432.CCR-25-3384) (2026) - Random forest classifier using the epigenetic instability index (EII) for cfDNA-based early cancer detection, achieving 81% sensitivity at 95% specificity for stage IA lung adenocarcinoma.
- [Learning Extremely Sparse Signals in High-Dimensional Cell-Free DNA Data Using Modern Hopfield Attention for Colorectal Cancer Detection](https://openreview.net/forum?id=tCYH1EdShW) (2026) - Fragment-Level Deep Learning uses Modern Hopfield Networks to identify extremely sparse tumor signal in cell-free DNA for colorectal cancer detection under a multiple-instance-learning setting.
- [Noninvasive detection and prognostic stratification of biliary tract cancer using cell-free DNA fragmentomics: a model development and validation study](https://doi.org/10.1186/s43556-026-00468-7) (2026) - Ensemble machine-learning model integrating copy number variation, fragment size distribution, and promoter fragmentation entropy for cfDNA fragmentomics-based biliary tract cancer detection achieving AUC 0.
<!-- AUTO-PAPERS:LIQUID_BIOPSY END -->

- [A deep multiple instance learning framework improves microsatellite instability detection from tumor next generation sequencing](https://www.nature.com/articles/s41467-023-35823-7) (2025) - MIL for MSI detection.
- [Large language model produces high accurate diagnosis of cancer from end-motif profiles of cell-free DNA](https://academic.oup.com/bib/article/25/5/bbae430/7747593) (2024) - LLM-based approach for cancer diagnosis using cfDNA end-motif profiles.
- [MethylGPT: a foundation model for the DNA methylome](https://www.biorxiv.org/content/10.1101/2024.10.30.621013v2) (2024) - A transformer-decoder-based LM pretrained on methylation microarray data.
- [Transformer-based representation learning and multiple-instance learning for cancer diagnosis exclusively from raw sequencing fragments of bisulfite-treated plasma cell-free DNA](https://febs.onlinelibrary.wiley.com/doi/10.1002/1878-0261.13745) (2024) - Transformer's encoder + attention-based MIL for CRC and HCC detection.
- [Deep generative AI models analyzing circulating orphan non-coding RNAs enable detection of early-stage lung cancer](https://www.nature.com/articles/s41467-024-53851-9) (2024) - VAE-based model for early lung cancer detection using circulating RNAs.
- [Transformer-based AI technology improves early ovarian cancer diagnosis using cfDNA methylation markers](https://www.sciencedirect.com/science/article/pii/S266637912400380X) (2024) - BERT-like model on CpG sites.
- [Development of a deep learning model for cancer diagnosis by inspecting cell-free DNA end-motifs](https://www.nature.com/articles/s41698-024-00635-5) (2024) - Transformer's encoder that captures end-motif signatures for HCC.
- [Deep learning model integrating cfDNA methylation and fragment size profiles for lung cancer diagnosis](https://www.nature.com/articles/s41598-024-63411-2) (2024) - CNN for lung cancer diagnosis.
- [Early detection of hepatocellular carcinoma via no end-repair enzymatic methylation sequencing of cell-free DNA and pre-trained neural network](https://genomemedicine.biomedcentral.com/articles/10.1186/s13073-023-01238-8) (2023) - BERT-like model for early HCC detection.
- [Comprehensive tissue deconvolution of cell-free DNA by deep learning for disease diagnosis and monitoring](https://www.pnas.org/doi/10.1073/pnas.2305236120) (2023) - MLE application in cfDNA tissue deconvolution.
- [MethylBERT: A Transformer-based model for read-level DNA methylation pattern identification and tumour deconvolution](https://www.nature.com/articles/s41467-025-55920-z) (2025) - BERT-like model pre-trained on human reference genome and adapted for methylation sequence profiles.
- [CpGPT](https://www.biorxiv.org/content/10.1101/2024.10.24.619766v1) (2024) - GPT-based foundation model pre-trained on large-scale CpG methylation array data for methylation imputation and biological age estimation.
- [EpiGePT](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-024-03449-7) (2024) - Transformer-based model for querying and predicting cell-type-specific epigenomic signals from DNA sequence context.
- [MethylQUEEN](https://www.biorxiv.org/content/10.1101/2024.12.26.630389v2) (2024) - Quintuple bidirectional transformer encoder for methylation sequence modeling; authors also released a companion cell-free multi-omics database.
- [Bridging biological cfDNA features and machine learning approaches](https://www.cell.com/trends/genetics/fulltext/S0168-9525(23)00019-7) (2023) - Background in Biology for ML practitioners.
- [The cell-free DNA methylome captures distinctions between localized and metastatic prostate tumors](https://www.nature.com/articles/s41467-022-34012-2) (2022) - Methylome analysis for prostate cancer staging.
- [Tumor fractions deciphered from circulating cell-free DNA methylation for cancer early diagnosis](https://www.nature.com/articles/s41467-022-35320-3) (2022) - Bayesian modeling for tumor fraction estimation.
- [DISMIR: Deep learning-based noninvasive cancer detection by integrating DNA sequence and methylation information of individual cell-free DNA reads](https://academic.oup.com/bib/article/22/6/bbab250/6318194) (2021) - Hybrid sequence model (ConvNet+LSTM) for HCC detection with maximization of tumor fraction posterior probability.
- [CancerDetector: ultrasensitive and non-invasive cancer detection at the resolution of individual reads using cell-free DNA methylation sequencing data](https://academic.oup.com/nar/article/46/15/e89/5036349) (2018) - Statistical model for read-level cancer detection from cfDNA.

### Novel Epigenetic Assays
<!-- AUTO-PAPERS:NOVEL_ASSAYS START -->
<!-- AUTO-PAPERS:NOVEL_ASSAYS END -->

- [Multimodal cell-free DNA whole-genome TAPS is sensitive and reveals specific cancer signals](https://www.nature.com/articles/s41467-024-55428-y) (2025) - Deep and less destructive assay than bisulfite sequencing.
- [Enzymatic methyl sequencing detects DNA methylation at single-base resolution from picograms of DNA](https://www.nature.com/articles/s41592-021-01103-7) (2021) - Enzymatic methyl sequencing.
- [scNMT-seq: Single-cell nucleosome, methylation and transcription sequencing](https://www.nature.com/articles/s41467-018-03149-4) (2018) - Single-cell nucleosome, methylation and transcription sequencing.
- [DNA methylation detection: Bisulfite genomic sequencing analysis](https://link.springer.com/protocol/10.1007/978-1-61779-316-5_2) (2011) - Background of bisulfite sequencing. Also check [Bisulfite_sequencing](https://en.wikipedia.org/wiki/Bisulfite_sequencing) and [Reduced representation bisulfite sequencing](https://en.wikipedia.org/wiki/Reduced_representation_bisulfite_sequencing) on Wiki.

## Datasets
<!-- AUTO-PAPERS:DATASETS START -->
<!-- AUTO-PAPERS:DATASETS END -->

- [ENCODE](https://www.encodeproject.org/) - Encyclopedia of DNA Elements.
- [Roadmap Epigenomics](http://www.roadmapepigenomics.org/) - Comprehensive reference maps of epigenomic states across 111 human reference epigenomes.
- [TCGA](https://www.cancer.gov/ccg/research/genome-sequencing/tcga)/[GDC](https://portal.gdc.cancer.gov/) - The Cancer Genome Atlas/Genomic Data Commons contains comprehensive multi-omics data including DNA methylation (450K/EPIC arrays), RNA-seq, WGS/WES, and clinical information across 33+ cancer types. Data can be accessed through GDC Data Portal or API.
- [GEO](https://www.ncbi.nlm.nih.gov/geo/) - Gene Expression Omnibus, contains various epigenetics datasets.
- [EWAS Atlas](https://bigd.big.ac.cn/ewas/) - A comprehensive database for epigenome-wide association studies.
- [ClockBase](http://gladyshevlab.org:3838/ClockBase/) - A curated methylation database for biological ages.
- [MethylBank](https://ngdc.cncb.ac.cn/methbank/) - A comprehensive database for DNA methylation data.
- [Loyfer et al. DNA methylation atlas of normal human cell types](https://www.nature.com/articles/s41586-022-05580-6#data-availability) (2023) - Whole-genome bisulfite sequencing atlas across 39 normal human cell types.
- [BLUEPRINT Epigenome Project](https://projects.ensembl.org/blueprint/) - Reference epigenomes for haematopoietic cell types including histone modifications, DNA methylation, and gene expression.

## Contributing

Your contributions are always welcome!

### Suggest a paper via an issue (easiest)

No git or pull request needed — just [open a Paper Suggestion issue](../../issues/new?template=paper_suggestion.yml) and paste one or more URLs or titles (DOIs, journal/arXiv/bioRxiv links, or OpenReview forum URLs). On submit, the bot will:

1. Resolve each paper's title, year, and **abstract** from public APIs (OpenAlex, Crossref, OpenReview)
2. Auto-assign a category and write a one-sentence description **grounded in the abstract**
3. Validate links and check for duplicates
4. Open a pull request that **closes your issue when it merges**

The PR runs the same review-gate checks and **auto-merges once they pass** — a maintainer only steps in if a check fails. Category is optional: pick one from the dropdown or leave it as **Unsure** and the bot will infer it (papers it still can't categorize are left out of the PR until you add a hint).

To re-run the bot after editing your issue, comment **`/triage`** (optionally followed by more URLs/titles); it updates the same pull request.

### Automated updates

New papers are discovered and proposed automatically twice a month via a GitHub Actions pipeline. The bot searches OpenAlex, Europe PMC, PubMed, arXiv, and bioRxiv, then screens candidates through rule-based scoring and a two-stage LLM review before opening a pull request. Each section contains a bot-owned sub-block between `<!-- AUTO-PAPERS:… START -->` and `<!-- AUTO-PAPERS:… END -->` comments — do not edit lines inside those markers by hand.

### Manual contributions

To add a resource yourself, open a pull request with your entry placed **below** the `<!-- AUTO-PAPERS:… END -->` marker in the relevant section (the bot-owned block of recent papers sits at the top of each section; older curated classics follow below it). The review-gate CI will run format, dedup, and link-reachability checks automatically.

Use this format:

`- [Title](https://doi.org/10.xxxx/xxxxx) (Year) - One-sentence description of the contribution.`

Guidelines:

1. Ensure your suggestion is not already included
2. Make one pull request per suggestion
3. Keep descriptions concise and accurate
4. Check spelling and grammar
5. Add to the most relevant category
6. Prefer DOI URLs (`https://doi.org/…`) over journal landing pages when available
