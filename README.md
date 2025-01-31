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
- [Epigenomic language models powered by Cerebras](https://arxiv.org/abs/2112.07571) (2021) - BERT model pretrained on human genome and across 127 cell types with DNA sequence and paired epigenetic state inputs. 
- [MethylNet: Deep learning for DNA methylation analysis](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-020-3443-8) (2020) - VAE for analyzing DNA methylation data.
- [DeepCpG: Accurate prediction of single-cell DNA methylation states using deep learning](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-017-1189-z) (2017) - CNN model for predicting single-cell DNA methylation states.
- [Detection of significantly differentially methylated regions in targeted bisulfite sequencing data](https://academic.oup.com/bioinformatics/article/29/13/1647/200453) (2013) - Stats model for identifying differentially methylated region (DMR) from microarray data (i.e. clustering/segment).
- [A nonparametric Bayesian approach for clustering bisulfate-based DNA methylation profiles](https://link.springer.com/article/10.1186/1471-2164-13-S6-S20) (2012) - Bayesian stats model for clustering/segment microarray data. 

### Histone Modifications

- [DeepHistone: A deep learning approach to predicting histone modifications](https://bmcgenomics.biomedcentral.com/articles/10.1186/s12864-019-5489-4) (2019) - CNN-based model for histone modification prediction.
- [DeepDiff: DEEP-learning for predicting DIFFerential gene expression from histone modifications](https://academic.oup.com/bioinformatics/article/34/17/i891/5093224) (2018) - Hybrid (attention + LSTM) deep learning model for gene expression prediction from histone modification.

### Chromatin Accessibility

- [Effective gene expression prediction from sequence by integrating long-range interactions](https://www.nature.com/articles/s41592-021-01252-x) (2021) - Transformer-based model for chromatin accessibility prediction.
- [DeepTACT: predicting 3D chromatin contacts via bootstrapping deep learning](https://academic.oup.com/nar/article/47/10/e60/5380496) (2019) - A bootstrapping deep learning model to predict chromatin contacts between regulatory elements.
- [cisTopic: cis-regulatory topic modeling on single-cell ATAC-seq data](https://www.nature.com/articles/s41592-019-0367-1) (2019) - A probabilistic framework used to simultaneously discover coaccessible enhancers and stable cell states from sparse single-cell epigenomics data.

### Multi-omics Integration
- [SCENIC+: single-cell multiomic inference of enhancers and gene regulatory networks](https://www.nature.com/articles/s41592-023-01938-4) (2021) - Gradient-boost regression model for single-cell multiomic inference of enhancers and gene regulatory networks. 
- [MOFA+: A probabilistic framework for comprehensive integration of structured single-cell data](https://genomebiology.biomedcentral.com/articles/10.1186/s13059-020-02015-1) (2020) - Framework for integrating multiple omics data types.

### Liquid Biopsy
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
- [MethylBERT: A Transformer-based model for read-level DNA methylation pattern identification and tumour deconvolution](https://www.biorxiv.org/content/10.1101/2023.10.29.564590v3) (2023, now available in [Nature Communications 2025](https://www.nature.com/articles/s41467-025-55920-z)) - BERT-like model pre-trained on human reference genome and adapted for methylation sequence profiles.
- [Bridging biological cfDNA features and machine learning approaches](https://www.cell.com/trends/genetics/fulltext/S0168-9525(23)00019-7) (2023) - Background in Biology for ML practitioners.
- [The cell-free DNA methylome captures distinctions between localized and metastatic prostate tumors](https://www.nature.com/articles/s41467-022-34012-2) (2022) - Methylome analysis for prostate cancer staging.
- [Tumor fractions deciphered from circulating cell-free DNA methylation for cancer early diagnosis](https://www.nature.com/articles/s41467-022-35320-3) (2022) - Bayesian modeling for tumor fraction estimation.
- [DISMIR: Deep learning-based noninvasive cancer detection by integrating DNA sequence and methylation information of individual cell-free DNA reads](https://academic.oup.com/bib/article/22/6/bbab250/6318194) (2021) - Hybrid sequence model (ConvNet+LSTM) for HCC detection with maximization of tumor fraction posterior probability.
- [CancerDetector: ultrasensitive and non-invasive cancer detection at the resolution of individual reads using cell-free DNA methylation sequencing data](https://academic.oup.com/nar/article/46/15/e89/5036349) (2018) - Statistical model for read-level cancer detection from cfDNA.

### Novel Epigenetic Assays
- [Multimodal cell-free DNA whole-genome TAPS is sensitive and reveals specific cancer signals](https://www.nature.com/articles/s41467-024-55428-y) (2025) - Deep and less destructive assay than bisulfite sequencing.
- [Enzymatic methyl sequencing detects DNA methylation at single-base resolution from picograms of DNA](https://www.nature.com/articles/s41592-021-01103-7) (2021) - Enzymatic methyl sequencing.
- [scNMT-seq: Single-cell nucleosome, methylation and transcription sequencing](https://www.nature.com/articles/s41467-018-03149-4) (2018) - Single-cell nucleosome, methylation and transcription sequencing.
- [DNA methylation detection: Bisulfite genomic sequencing analysis](https://link.springer.com/protocol/10.1007/978-1-61779-316-5_2) (2011) - Background of bisulfite sequencing. Also check [Bisulfite_sequencing](https://en.wikipedia.org/wiki/Bisulfite_sequencing) and [Reduced representation bisulfite sequencing](https://en.wikipedia.org/wiki/Reduced_representation_bisulfite_sequencing) on Wiki.

## Datasets

- [ENCODE](https://www.encodeproject.org/) - Encyclopedia of DNA Elements.
- [Roadmap Epigenomics](http://www.roadmapepigenomics.org/) - Comprehensive mapping of epigenomic states.
- [GEO](https://www.ncbi.nlm.nih.gov/geo/) - Gene Expression Omnibus, contains various epigenetics datasets.
- [EWAS Atlas](https://bigd.big.ac.cn/ewas/) - A comprehensive database for epigenome-wide association studies.
- [ClockBase](http://gladyshevlab.org:3838/ClockBase/) - A curated methylation database for biological ages.

## Contributing

Your contributions are always welcome! Please following the guidelines to contribute.

### Guidelines for Contributing

1. Ensure your suggestion is not already included
2. Make an individual pull request for each suggestion
3. Use the following format: `[Resource Name](Link) (Year) - Description.`
4. Keep descriptions concise and clear
5. Check your spelling and grammar
6. Make sure your text editor is set to remove trailing whitespace
7. Add your suggestion to the most relevant category
