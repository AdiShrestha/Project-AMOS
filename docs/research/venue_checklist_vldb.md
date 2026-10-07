# VLDB 2027 Venue Compliance & Submission Readiness Checklist

**Target Venue**: 53rd International Conference on Very Large Data Bases (VLDB 2027) / Proceedings of the VLDB Endowment (PVLDB)  
**Submission Category**: Research Track — Experiment, Analysis & Benchmark (EAB) Category  
**Document**: `docs/research/venue_checklist_vldb.md`  

---

## 1. Track Fit & Category Justification

### 1.1 Category Choice: Experiment, Analysis & Benchmark (EAB)
- **Primary Focus**: BPFeat is a systems-level experimental evaluation and comparative benchmarking paper investigating the feature freshness vs. write-transport trade-off in streaming recommender pipelines.
- **Experimental Rigor**: The paper evaluates an exhaustive confirmatory matrix of 35 trials across 5 seeds and 46 independent hourly clusters, benchmarking against both prospectively tuned static baselines ($U^*=20$) and work-budget-matched controls ($WWR=0.3302$).
- **Benchmark Completeness**: Incorporates systems metrics (write work ratio, staleness distributions, query coverage) alongside ranking metrics (Average Precision, AUROC, Log Loss, Brier score).
- **Scope Alignment**: Fully aligns with the PVLDB EAB charter calling for "methodologically sound, thorough performance comparisons of existing algorithms and systems under real-world workloads."

---

## 2. Formal Submission Requirements Checklist

| Requirement | Policy Description | Project AMOS Implementation Status | Compliance |
| :--- | :--- | :--- | :---: |
| **Page Limit** | Max 12 pages for main content + unlimited pages for references/appendix | Manuscript is within the 12-page research paper body limit. | **COMPLIANT** |
| **Formatting** | Standard ACM SIGCONF / PVLDB two-column layout | Structured standard ACM markdown format mapped to PVLDB styles. | **COMPLIANT** |
| **Double-Anonymous Review** | No author names, affiliations, or institutional identifiers | Author list marked *"Anonymous for Double-Anonymous Review"*; repo references anonymized or clean. | **COMPLIANT** |
| **Citations to Own Work** | Refer to prior work in third person | Prior works cited in standard third person format. | **COMPLIANT** |
| **Artifact Availability** | Public repository and verifiable reproduction recipe | Standalone reproduction verifier (`tools/reproduction_verifier.py`) and scripts provided. | **COMPLIANT** |
| **Conflict of Interest (COI)** | Institutional, advisor, and co-author COI declarations | Authors declare standard COIs during conference portal upload. | **COMPLIANT** |
| **Human Subjects & Ethics** | User data privacy and anonymization compliance | Tianchi dataset contains hashed, pseudo-anonymized user/item identifiers; no PII. | **COMPLIANT** |

---

## 3. Disclaimers & Integrity Notices

### 3.1 Non-Fabrication & Evidence Audit
All reported quantitative statistics in the manuscript originate from logged raw trial executions. No values were generated post-hoc or inferred from marketing specifications.

### 3.2 Acceptance Disclaimer
> **Important Scholarly Notice**: Passing mechanical factory pre-submission audits, Gatekeeper checks, and reproduction tests demonstrates software correctness, internal consistency, and reproducible scientific accounting. It does **not** constitute or guarantee scholarly peer-review acceptance by the VLDB 2027 program committee, which evaluates subjective novelty, broader community interest, and peer comparative merit.
