"""
preprocess.py  –  TQIP Spleen Injury Study Preprocessing Pipeline
Python/pandas translation of the R script:
  TqipFeb19h1_June28c_partofJuly2submitted_...Oct19_2024e_redidTqipValues7.R

Expected project layout
-----------------------
Trauma-Project/
├── all_with_comp_from_puf.csv        # master dataset built by build_master.py
├── Dataset 2/PUF AY YYYY/CSV/
│       PUF_ECODEDES.csv              # E-code descriptions / INJTYPE lookup
├── Dataset 3/PUF AY YYYY/CSV/        # 2016-format layout
│       TQP_INCLUSION.csv             # TQIP inclusion criteria
├── Dataset 3/PUFAYYYYYYY/            # 2024-format layout
│       TQP_INCLUSION.csv

Year folders named "PUF AY YYYY" and "PUFAYYYYYYY" are both discovered
automatically and concatenated.

Outputs
-------
tqip13_feb14_nonpenetrating1.csv  – 65 k-row intermediate (after exclusions)
tqip13_final.csv                  – ~41 187-row final dataset
"""

import sys
import re
from pathlib import Path

import numpy as np
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
PROJECT_ROOT  = Path(__file__).parent
MASTER_EXCEL  = PROJECT_ROOT / "all_with_comp_02112023.xlsx"
MASTER_CSV    = PROJECT_ROOT / "all_with_comp_from_puf.csv"   # built by build_master.py

DIR_LOOKUP    = PROJECT_ROOT / "Dataset 2"   # ECODEDES
DIR_ECODE_ED  = PROJECT_ROOT / "Dataset 3"   # ECODE, ED, TQP_INCLUSION
DIR_PM        = PROJECT_ROOT / "Dataset 4"   # PUF_PM, PUF_PCODE (2016)
ICDPROC_2024  = PROJECT_ROOT / "Dataset" / "PUFAY2024" / "PUF_ICDPROCEDURE.csv"

OUT_INTERMEDIATE = PROJECT_ROOT / "tqip13_feb14_nonpenetrating1.csv"
OUT_FINAL        = PROJECT_ROOT / "tqip13_final.csv"

# ── Comorbidity / complication column definitions ─────────────────────────────
# R script: tqip1[,107:134]  → 28 comorbidity indicator columns named comorb{n}
# R script: tqip1[,135:159]  → 25 complication indicator columns named compl{n}
# Specific variables referenced in the R code:
COMORB_COLS = [
    "comorb2",  "comorb3",  "comorb4",  "comorb5",  "comorb6",
    "comorb7",  "comorb8",  "comorb9",  "comorb10", "comorb11",
    "comorb12", "comorb13", "comorb15", "comorb16", "comorb17",
    "comorb18", "comorb19", "comorb21", "comorb22", "comorb23",
    "comorb24", "comorb25", "comorb26", "comorb27", "comorb28",
    "comorb29", "comorb30", "comorb1",
]  # 28 entries; fall back to regex discovery if these names are absent

COMPL_COLS = [
    "compl1",  "compl4",  "compl5",  "compl8",  "compl11",
    "compl12", "compl13", "compl14", "compl15", "compl18",
    "compl19", "compl20", "compl21", "compl22", "compl23",
    "compl25", "compl27", "compl28", "compl29", "compl30",
    "compl31", "compl32", "compl33", "compl34", "compl35",
]  # 25 entries


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def _shape_msg(df: pd.DataFrame, label: str) -> None:
    print(f"  [{label}]  rows={df.shape[0]:>7,}  cols={df.shape[1]}")


def _find_year_dirs(base: Path) -> list[Path]:
    """Return sorted list of year directories inside *base*.

    Handles both classic 'PUF AY YYYY' layout (2016) and the compact
    'PUFAYYYYYYY' layout used from 2024 onward.
    """
    dirs = sorted([d for d in base.glob("PUF AY *") if d.is_dir()])
    dirs += sorted([d for d in base.glob("PUFAY*") if d.is_dir()])
    if not dirs:
        print(f"  WARNING: no year directories found under {base}")
    return dirs


def _load_year_csvs(
    base_dir: Path,
    filename: str,
    usecols: list[str] | None = None,
) -> pd.DataFrame:
    """
    Load *filename* from every year sub-directory under *base_dir*.
    Tries base_dir/year/CSV/filename (2016 layout) then base_dir/year/filename
    (2024 layout).  Concatenates all available years into one DataFrame.
    Column names are normalised to upper-case.
    """
    frames = []
    for year_dir in _find_year_dirs(base_dir):
        # Classic layout: year_dir/CSV/filename
        csv_path = year_dir / "CSV" / filename
        if not csv_path.exists():
            # Compact 2024 layout: year_dir/filename
            csv_path = year_dir / filename
        if not csv_path.exists():
            print(f"  WARNING: {filename} not found in {year_dir.name} – skipping")
            continue
        df = pd.read_csv(csv_path, usecols=usecols, low_memory=False)
        df.columns = df.columns.str.upper()
        # Derive admission year from folder name ("PUF AY 2016" → 2016, "PUFAY2024" → 2024)
        try:
            df["_AY"] = int(year_dir.name.split()[-1])
        except ValueError:
            pass
        frames.append(df)
        print(f"  Loaded {csv_path.name} from {year_dir.name}: {len(df):,} rows")

    if not frames:
        raise FileNotFoundError(
            f"No '{filename}' files found in any year directory under {base_dir}"
        )
    combined = pd.concat(frames, ignore_index=True)
    # Deduplicate in case the same INC_KEY appears in multiple year files
    return combined


def _discover_indicator_cols(df: pd.DataFrame, pattern: str) -> list[str]:
    """Return column names matching *pattern* regex, sorted numerically."""
    cols = [c for c in df.columns if re.fullmatch(pattern, c, re.IGNORECASE)]
    cols.sort(key=lambda c: int(re.search(r"\d+", c).group()))
    return cols


# ─────────────────────────────────────────────────────────────────────────────
# Step 1  –  Load master dataset and E-code files; join on INC_KEY
# ─────────────────────────────────────────────────────────────────────────────

def step1_load_and_join_ecodes(master: pd.DataFrame) -> pd.DataFrame:
    """
    R equivalent
    ─────────────
    e_code_des <- read.csv('PUF_ECODEDES.csv')
    e_code16   <- read.csv('PUF_ECODE_2016.csv')
    tqip1_ecodes <- left_join(master, e_code16, by = 'INC_KEY')

    Builds the set of penetrating E-codes from PUF_ECODEDES.csv.
    Per-patient ECODE/ECODE2 are already present in the CSV master built by
    build_master.py, so the PUF_ECODE.csv join is skipped to avoid row
    duplication (PUF_ECODE has multiple rows per patient).
    """
    print("\n── Step 1: Load E-codes and join with master dataset ──")

    # 1a. E-code descriptions (INJTYPE lookup) – any year's copy is fine
    ecodedes_path = None
    for year_dir in _find_year_dirs(DIR_LOOKUP):
        for candidate in (year_dir / "CSV" / "PUF_ECODEDES.csv",
                          year_dir / "PUF_ECODEDES.csv"):
            if candidate.exists():
                ecodedes_path = candidate
                break
        if ecodedes_path:
            break
    if ecodedes_path is None:
        raise FileNotFoundError("PUF_ECODEDES.csv not found under Dataset 2/")

    ecodedes = pd.read_csv(ecodedes_path, low_memory=False)
    ecodedes.columns = ecodedes.columns.str.upper()
    ecodedes = ecodedes[["ECODE", "INJTYPE"]].dropna(subset=["INJTYPE"])
    ecodedes = ecodedes[ecodedes["ECODE"].notna()]
    ecodedes["ECODE"] = pd.to_numeric(ecodedes["ECODE"], errors="coerce")
    penetrating_ecodes = set(
        ecodedes.loc[ecodedes["INJTYPE"].str.strip() == "Penetrating", "ECODE"].dropna()
    )
    print(f"  Penetrating E-code count in lookup: {len(penetrating_ecodes):,}")

    # 1b. ECODE/ECODE2 are already present in the master CSV (built by
    #     build_master.py).  Joining PUF_ECODE.csv again would multiply rows
    #     (the file has one row per E-code, not per patient).
    if "ECODE" in master.columns:
        print("  ECODE already in master – skipping PUF_ECODE.csv join")
        df = master.copy()
    else:
        ecode_all = _load_year_csvs(DIR_ECODE_ED, "PUF_ECODE.csv")
        ecode_all["ECODE"]  = pd.to_numeric(ecode_all["ECODE"],  errors="coerce")
        ecode_all["ECODE2"] = pd.to_numeric(
            ecode_all.get("ECODE2", pd.Series(dtype=float)), errors="coerce"
        )
        df = master.merge(ecode_all[["INC_KEY", "ECODE", "ECODE2"]],
                          on="INC_KEY", how="left", suffixes=("", "_ecode"))

    _shape_msg(df, "after ECODE step")

    # Attach the penetrating E-code set as metadata on the frame for step 3
    df.attrs["penetrating_ecodes"] = penetrating_ecodes
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Step 2  –  Load ED transfer data; join TRANSFER column onto master
# ─────────────────────────────────────────────────────────────────────────────

def step2_load_transfer(df: pd.DataFrame) -> pd.DataFrame:
    """
    R equivalent
    ─────────────
    ed16 <- PUF_ED_16 %>% select(INC_KEY, TRANSFER)
    df   <- left_join(df, ed16, by = 'INC_KEY')

    TRANSFER is already in the master CSV (built by build_master.py from
    PUF_ED.csv for 2016 and INTERFACILITYTRANSFER for 2024).  We create
    OverallTransfer directly from that column rather than re-joining.
    """
    print("\n── Step 2: Load ED transfer data ──")

    if "TRANSFER" in df.columns:
        print("  TRANSFER already in master – using as OverallTransfer")
        df = df.copy()
        df["OverallTransfer"] = df["TRANSFER"]
    else:
        ed_all = _load_year_csvs(DIR_ECODE_ED, "PUF_ED.csv", usecols=None)
        ed_transfer = (
            ed_all[["INC_KEY", "TRANSFER"]]
            .drop_duplicates(subset="INC_KEY", keep="first")
        )
        df = df.merge(ed_transfer, on="INC_KEY", how="left", suffixes=("", "_ed"))
        transfer_cols = [c for c in df.columns if c.startswith("TRANSFER")]
        if transfer_cols:
            df["OverallTransfer"] = df[transfer_cols[0]]
            for col in transfer_cols[1:]:
                df["OverallTransfer"] = df["OverallTransfer"].combine_first(df[col])
            df.drop(columns=[c for c in transfer_cols if c != "OverallTransfer"],
                    inplace=True, errors="ignore")

    _shape_msg(df, "after TRANSFER step")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Step 3  –  Filter to non-penetrating trauma
# ─────────────────────────────────────────────────────────────────────────────

def step3_filter_nonpenetrating(df: pd.DataFrame) -> pd.DataFrame:
    """
    R equivalent
    ─────────────
    target_penetrating <- e_code_des_penetrating$ECODE
    tqip1_penetrating  <- tqip1_ecodes %>%
        filter(ECODE.x %in% target_penetrating | ECODE2.x %in% target_penetrating | ...)
    nonpenetrating <- anti_join(tqip1, tqip1_penetrating, by = 'INC_KEY')
    tqip1 <- nonpenetrating

    A patient is penetrating if *any* of their E-code fields matches a
    penetrating code. We then EXCLUDE those patients (anti-join).
    """
    print("\n── Step 3: Filter to non-penetrating trauma ──")

    penetrating_ecodes = df.attrs.get("penetrating_ecodes", set())

    ecode_cols = [c for c in df.columns if re.fullmatch(r"ECODE2?(_\w+)?", c)]
    print(f"  E-code columns used for penetrating check: {ecode_cols}")

    is_penetrating = pd.Series(False, index=df.index)

    # Numeric E-code check (2016 data: ECODE/ECODE2 are integers)
    if penetrating_ecodes:
        for col in ecode_cols:
            numeric_col = pd.to_numeric(df[col], errors="coerce")
            is_penetrating |= numeric_col.isin(penetrating_ecodes)
    else:
        print("  WARNING: penetrating E-code set is empty – relying on INJTYPE only")

    # Text INJTYPE check (2024 data: ECODE is ICD-10 string, INJTYPE already decoded)
    if "INJTYPE" in df.columns:
        print("  Also checking INJTYPE column for 2024 penetrating injuries")
        is_penetrating |= (df["INJTYPE"].astype(str).str.strip() == "Penetrating")

    n_before = len(df)
    df = df[~is_penetrating].copy()
    print(f"  Removed {n_before - len(df):,} penetrating-trauma patients")
    _shape_msg(df, "non-penetrating")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Step 4  –  Feature engineering
# ─────────────────────────────────────────────────────────────────────────────

def step4_feature_engineering(df: pd.DataFrame) -> pd.DataFrame:
    """
    R equivalent
    ─────────────
    # Comorbidity sum (28 columns, positions 107-134 in master Excel)
    tqip14  <- tqip1[, 107:134]
    tqip14a <- as.data.frame(lapply(tqip14, as.numeric))
    tqip14b <- tqip14a %>% mutate(comordes_sum = rowSums(tqip14a, na.rm=TRUE))
    df$comordes_yes <- ifelse(comordes_sum != 0, 1, 0)

    # Complication sum (25 columns, positions 135-159)
    tqip15  <- tqip1[, 135:159]
    tqip15a <- as.data.frame(lapply(tqip15, as.numeric))
    tqip15b <- tqip15a %>% mutate(complications_sum = rowSums(tqip15a, na.rm=TRUE))
    df$complications_yes <- ifelse(complications_sum != 0, 1, 0)

    # Replace NA transfusion values with 0, binary-encode
    df$TRANS_BLOOD_4HOURS    <- ifelse(TRANS_BLOOD_4HOURS    != 0, 1, 0)
    df$TRANS_PLASMA_4HOURS   <- replace(-1 with 0); ifelse(!= 0, 1, 0)
    df$TRANS_PLATELETS_4HOURS <- replace(-1 with 0); ifelse(!= 0, 1, 0)
    """
    print("\n── Step 4: Feature engineering ──")

    # ── 4a. Comorbidity indicators → comordes_sum, comordes_yes ────────────
    # Prefer explicitly named columns; fall back to regex discovery
    present_comorb = [c for c in COMORB_COLS if c in df.columns]
    if not present_comorb:
        present_comorb = _discover_indicator_cols(df, r"comorb\d+")
    if not present_comorb:
        print("  WARNING: no comorbidity columns found – comordes_sum set to 0")
        df["comordes_sum"] = 0
    else:
        print(f"  Comorbidity columns found: {len(present_comorb)} "
              f"({present_comorb[0]} … {present_comorb[-1]})")
        comorb_numeric = df[present_comorb].apply(pd.to_numeric, errors="coerce").fillna(0)
        df["comordes_sum"] = comorb_numeric.sum(axis=1)

    df["comordes_yes"] = (df["comordes_sum"] != 0).astype(int)
    print(f"  comordes_sum: mean={df['comordes_sum'].mean():.3f}, "
          f"any_comorb_pct={df['comordes_yes'].mean()*100:.1f}%")

    # ── 4b. Complication indicators → complications_sum, complications_yes ──
    present_compl = [c for c in COMPL_COLS if c in df.columns]
    if not present_compl:
        present_compl = _discover_indicator_cols(df, r"compl\d+")
    if not present_compl:
        print("  WARNING: no complication columns found – complications_sum set to 0")
        df["complications_sum"] = 0
    else:
        print(f"  Complication columns found: {len(present_compl)} "
              f"({present_compl[0]} … {present_compl[-1]})")
        compl_numeric = df[present_compl].apply(pd.to_numeric, errors="coerce").fillna(0)
        df["complications_sum"] = compl_numeric.sum(axis=1)

    df["complications_yes"] = (df["complications_sum"] != 0).astype(int)
    print(f"  complications_sum: mean={df['complications_sum'].mean():.3f}, "
          f"any_compl_pct={df['complications_yes'].mean()*100:.1f}%")

    # ── 4c. Replace NA / sentinel values in comorbidity / complication columns
    # R: comorb4 %>% replace_na(0)  (for all individual comorbidity cols)
    for col in present_comorb + present_compl:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # ── 4d. Binary-encode transfusion amounts ───────────────────────────────
    # R: TRANS_PLASMA_4HOURS   <- mutate(replace == -1 → 0); ifelse(!= 0, 1, 0)
    # R: TRANS_PLATELETS_4HOURS <- same
    # R: TRANS_BLOOD_4HOURS     <- ifelse(!= 0, 1, 0)  (no -1 replacement needed)
    for col in ["TRANS_PLASMA_4HOURS", "TRANS_PLATELETS_4HOURS"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            df[col] = df[col].replace(-1, 0)

    for col in ["TRANS_BLOOD_4HOURS", "TRANS_PLASMA_4HOURS", "TRANS_PLATELETS_4HOURS"]:
        if col in df.columns:
            df[col] = (df[col].fillna(0) != 0).astype(int)

    if "TRANS_BLOOD_4HOURS" in df.columns:
        print(f"  Transfusion binary rates – "
              f"Blood: {df['TRANS_BLOOD_4HOURS'].mean()*100:.1f}%  "
              f"Plasma: {df['TRANS_PLASMA_4HOURS'].mean()*100:.1f}%  "
              f"Platelets: {df['TRANS_PLATELETS_4HOURS'].mean()*100:.1f}%")

    _shape_msg(df, "after feature engineering")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Step 5  –  Sequential exclusion pipeline
# ─────────────────────────────────────────────────────────────────────────────

def step5_sequential_exclusions(df: pd.DataFrame) -> pd.DataFrame:
    """
    R equivalent (sequential filters with printed counts after each)
    ─────────────
    tqip2  <- tqip1e %>% filter(death1 != 1)        # remove ED deaths
    tqip3  <- tqip2  %>% select(...)                 # column selection
    tqip4  <- tqip3  %>% filter(!is.na(ISSAIS))      # remove missing ISS
    tqip4a <- tqip4  %>% filter(!is.na(spleenseverity))
    tqip10e <- ... %>% filter(!is.na(ED_PULSE))
    tqip10f <- ... %>% filter(!is.na(ED_Sbp))

    Prints the row count after each exclusion step.
    """
    print("\n── Step 5: Sequential exclusion pipeline ──")

    exclusions = [
        # (description, column, condition)
        ("Remove ED deaths (death1 == 1)",    "death1",        lambda s: s == 1),
        ("Remove missing ISSAIS",             "ISSAIS",        lambda s: s.isna()),
        ("Remove missing spleenseverity",     "spleenseverity",lambda s: s.isna()),
        ("Remove missing ED_PULSE",           "ED_PULSE",      lambda s: s.isna()),
        ("Remove missing ED_Sbp",             "ED_Sbp",        lambda s: s.isna()),
    ]

    print(f"  Starting N: {len(df):,}")
    for description, col, condition_fn in exclusions:
        if col not in df.columns:
            print(f"  SKIP [{description}] – column '{col}' not in dataset")
            continue
        col_series = pd.to_numeric(df[col], errors="coerce") if col in ("death1", "ISSAIS", "spleenseverity", "ED_PULSE", "ED_Sbp") else df[col]
        n_before = len(df)
        df = df[~condition_fn(col_series)].copy()
        removed = n_before - len(df)
        print(f"  {description}: removed {removed:,} → remaining {len(df):,}")

    _shape_msg(df, "after exclusions (intermediate file)")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Step 5b  –  Assign treatment group g (1–4) from procedure codes
# ─────────────────────────────────────────────────────────────────────────────

def step5b_assign_treatment_group(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derives the treatment group variable g for each spleen-injury patient.

    Groups (confirmed from R-script plot labels "nonop","angio","surgery","surgery+angio"):
      g=1  NOM / observation   – no surgery, no angiography
      g=2  Angiography only    – angiography but no spleen surgery
      g=3  Surgery only        – splenectomy or splenorrhaphy, no angiography
      g=4  Surgery + Angio     – both surgery and angiography

    Surgery detection:
      ICD-9  41.5 / 41.43 (splenectomy), 41.95 (splenorrhaphy)
      ICD-10-PCS  07TP* (splenectomy), 07QP* (splenorrhaphy)

    Angiography detection:
      ICD-10-PCS  04L4* (splenic artery occlusion / embolization)
      ICD-9       38.86, 39.79, 88.47, 88.40, 88.41, 88.48, 88.49  (vascular/angio)
      2024 master ANGIOGRAPHY column ≥ 2

    Sources:
      2016  →  Dataset 4 / PUF AY 2016 / CSV / PUF_PCODE.csv
      2024  →  Dataset/PUFAY2024/PUF_ICDPROCEDURE.csv
               + ANGIOGRAPHY column already in master CSV
    """
    print("\n── Step 5b: Assign treatment group (g) from procedure codes ──")

    inc_keys_2016 = set(df.loc[df["AY"] == 2016, "INC_KEY"].dropna())
    inc_keys_2024 = set(df.loc[df["AY"] == 2024, "INC_KEY"].dropna())
    print(f"  Patients: 2016={len(inc_keys_2016):,}  2024={len(inc_keys_2024):,}")

    surgery_keys: set = set()   # splenectomy OR splenorrhaphy
    angio_keys:   set = set()

    # ICD-9 angiography codes found in g=2 patients in the original R study
    ICD9_ANGIO = {38.86, 39.79, 88.47, 88.40, 88.41, 88.48, 88.49, 39.5, 44.44}

    # ── 2016: PUF_PCODE.csv ───────────────────────────────────────────────────
    for year_dir in _find_year_dirs(DIR_PM):
        pcode_path = year_dir / "CSV" / "PUF_PCODE.csv"
        if not pcode_path.exists():
            continue
        pc_df = pd.read_csv(pcode_path, low_memory=False)
        pc_df.columns = pc_df.columns.str.upper()
        pc_df["INC_KEY"] = pd.to_numeric(pc_df["INC_KEY"], errors="coerce")
        pc_df = pc_df[pc_df["INC_KEY"].isin(inc_keys_2016)]
        print(f"  Loaded PUF_PCODE from {year_dir.name}: {len(pc_df):,} rows "
              f"for {pc_df['INC_KEY'].nunique():,} patients")

        # ICD-9 procedure codes
        if "PCODE" in pc_df.columns:
            icd9 = pd.to_numeric(pc_df["PCODE"], errors="coerce")
            surgery_keys.update(
                pc_df.loc[icd9.isin([41.5, 41.43, 41.95]), "INC_KEY"].dropna()
            )
            angio_keys.update(
                pc_df.loc[icd9.isin(ICD9_ANGIO), "INC_KEY"].dropna()
            )

        # ICD-10-PCS codes (also present in 2016 file)
        if "ICD10_PCODE" in pc_df.columns:
            icd10 = pc_df["ICD10_PCODE"].astype(str).str.strip().str.upper()
            surgery_keys.update(
                pc_df.loc[icd10.str.startswith("07TP") | icd10.str.startswith("07QP"),
                           "INC_KEY"].dropna()
            )
            angio_keys.update(
                pc_df.loc[icd10.str.startswith("04L4"), "INC_KEY"].dropna()
            )

    # ── 2024: ANGIOGRAPHY column already in master CSV ────────────────────────
    # ANGIOGRAPHY: 2=Angiogram only, 3=Angiogram+embolization, 4=Angiogram+stenting
    if "ANGIOGRAPHY" in df.columns:
        angio_numeric = pd.to_numeric(df.loc[df["AY"] == 2024, "ANGIOGRAPHY"],
                                      errors="coerce")
        angio_from_master = set(
            df.loc[(df["AY"] == 2024) & (angio_numeric >= 2), "INC_KEY"].dropna()
        )
        angio_keys.update(angio_from_master)
        print(f"  2024 ANGIOGRAPHY ≥ 2 from master: {len(angio_from_master):,} patients")

    # ── 2024: PUF_ICDPROCEDURE.csv ───────────────────────────────────────────
    if inc_keys_2024 and ICDPROC_2024.exists():
        n_chunks = 0
        for chunk in pd.read_csv(ICDPROC_2024, chunksize=500_000, low_memory=False):
            chunk.columns = chunk.columns.str.upper()
            chunk["INC_KEY"] = pd.to_numeric(chunk["INC_KEY"], errors="coerce")
            chunk = chunk[chunk["INC_KEY"].isin(inc_keys_2024)]
            if chunk.empty:
                n_chunks += 1
                continue
            icd10 = chunk["ICDPROCEDURECODE"].astype(str).str.strip().str.upper()
            surgery_keys.update(
                chunk.loc[icd10.str.startswith("07TP") | icd10.str.startswith("07QP"),
                           "INC_KEY"].dropna()
            )
            angio_keys.update(
                chunk.loc[icd10.str.startswith("04L4"), "INC_KEY"].dropna()
            )
            n_chunks += 1
        print(f"  2024 PUF_ICDPROCEDURE: read {n_chunks} chunks")
    elif inc_keys_2024:
        print(f"  WARNING: {ICDPROC_2024} not found – 2024 g may be incomplete")

    # ── Assign g based on surgery × angiography combination ──────────────────
    # g=1: no surgery, no angio   g=2: angio only
    # g=3: surgery only           g=4: surgery + angio
    df = df.copy()
    has_surgery = df["INC_KEY"].isin(surgery_keys)
    has_angio   = df["INC_KEY"].isin(angio_keys)

    df["g"] = 1
    df.loc[~has_surgery &  has_angio, "g"] = 2
    df.loc[ has_surgery & ~has_angio, "g"] = 3
    df.loc[ has_surgery &  has_angio, "g"] = 4

    print(f"\n  Surgery keys found : {len(surgery_keys):,}  "
          f"(ICD-9: 41.5/41.43/41.95 | ICD-10: 07TP*/07QP*)")
    print(f"  Angio keys found   : {len(angio_keys):,}  "
          f"(ICD-9: 38.86/39.79/88.4x | ICD-10: 04L4* | 2024 ANGIOGRAPHY≥2)")
    print(f"\n  g=1 NOM            : {df['g'].eq(1).sum():>8,}")
    print(f"  g=2 Angio only     : {df['g'].eq(2).sum():>8,}")
    print(f"  g=3 Surgery only   : {df['g'].eq(3).sum():>8,}")
    print(f"  g=4 Surgery+Angio  : {df['g'].eq(4).sum():>8,}")

    _shape_msg(df, "after g assignment")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Step 6  –  Apply TQIP inclusion criteria
# ─────────────────────────────────────────────────────────────────────────────

def step6_tqip_inclusion(df: pd.DataFrame) -> pd.DataFrame:
    """
    R equivalent
    ─────────────
    TQP_INCLUSION_13 <- read.csv('.../TQP_INCLUSION.csv')
    # cbind PEDSTQIP=NA, L3TQIP=NA for older years that lack those columns
    tqip_inclusion13_16 <- rbind(TQP_INCLUSION_13, ..., TQP_INCLUSION_16)
    tqip_inclusion13_16a <- tqip_inclusion13_16 %>%
        filter(ADULTTQIP == 'Yes' | PEDSTQIP == 'Yes' | L3TQIP == 'Yes')
    tqip13 <- tqip13 %>%
        filter(INC_KEY %in% tqip_inclusion13_16a$INC_KEY)

    Loads TQP_INCLUSION files for all available years, retains patients that
    meet any of the three inclusion criteria, then filters the main dataset.
    """
    print("\n── Step 6: Apply TQIP inclusion criteria ──")

    inclusion_frames = []
    for year_dir in _find_year_dirs(DIR_ECODE_ED):
        # Try classic CSV/ subdirectory first (2016), then direct path (2024)
        path = year_dir / "CSV" / "TQP_INCLUSION.csv"
        if not path.exists():
            path = year_dir / "TQP_INCLUSION.csv"
        if not path.exists():
            print(f"  WARNING: TQP_INCLUSION.csv not found in {year_dir.name} – skipping")
            continue
        inc = pd.read_csv(path, low_memory=False)
        inc.columns = inc.columns.str.upper()

        # The 2016 file uses 'INC_KEY' (lowercase in file → upper after strip),
        # but the column is named 'INC_KEY'. Normalise the key column name.
        key_col = next((c for c in inc.columns if c.upper() in ("INC_KEY", "INCKEY")), None)
        if key_col is None:
            print(f"  WARNING: no INC_KEY column in {path} – skipping")
            continue
        inc = inc.rename(columns={key_col: "INC_KEY"})

        # Older years (2013) lack PEDSTQIP and L3TQIP; add them as NA so
        # rbind-equivalent (pd.concat) works cleanly
        for missing_col in ("ADULTTQIP", "PEDSTQIP", "L3TQIP"):
            if missing_col not in inc.columns:
                inc[missing_col] = np.nan

        inclusion_frames.append(inc[["INC_KEY", "ADULTTQIP", "PEDSTQIP", "L3TQIP"]])
        print(f"  Loaded TQP_INCLUSION from {year_dir.name}: {len(inc):,} rows")

    if not inclusion_frames:
        raise FileNotFoundError("No TQP_INCLUSION.csv files found in Dataset 3/")

    inclusion = pd.concat(inclusion_frames, ignore_index=True)

    # Keep patients meeting any inclusion criterion.
    # 2016 files use "Yes"/"No" strings; 2024 files use 1/0 integers.
    def _is_yes(col: pd.Series) -> pd.Series:
        return (col.astype(str).str.strip().str.lower() == "yes") | (
            pd.to_numeric(col, errors="coerce").fillna(0) == 1
        )

    meets_criteria = (
        _is_yes(inclusion["ADULTTQIP"]) |
        _is_yes(inclusion["PEDSTQIP"])  |
        _is_yes(inclusion["L3TQIP"])
    )
    eligible_keys = set(inclusion.loc[meets_criteria, "INC_KEY"])
    print(f"  Eligible INC_KEYs (meets ≥1 criterion): {len(eligible_keys):,}")

    n_before = len(df)
    df = df[df["INC_KEY"].isin(eligible_keys)].copy()
    print(f"  Removed {n_before - len(df):,} patients not meeting TQIP criteria")
    _shape_msg(df, "final dataset")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Step 7  –  Load master dataset (entry point helper)
# ─────────────────────────────────────────────────────────────────────────────

def load_master() -> pd.DataFrame:
    """
    Load the master dataset from all_with_comp_from_puf.csv (built by build_master.py).
    Column names are stripped of whitespace; INC_KEY normalised to numeric.
    """
    print("\n── Loading master dataset ──")
    if not MASTER_CSV.exists():
        raise FileNotFoundError(
            f"Master CSV not found: {MASTER_CSV}\n"
            f"Run:  python build_master.py"
        )
    print(f"  Source: {MASTER_CSV.name}")
    df = pd.read_csv(MASTER_CSV, low_memory=False)
    df.columns = [c.strip() for c in df.columns]
    df["INC_KEY"] = pd.to_numeric(df["INC_KEY"], errors="coerce")
    _shape_msg(df, "master dataset loaded")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("TQIP Spleen Injury Study – Preprocessing Pipeline")
    print("=" * 60)

    # ── Load master ──────────────────────────────────────────────────────────
    df = load_master()

    # ── Step 1: E-codes ──────────────────────────────────────────────────────
    df = step1_load_and_join_ecodes(df)

    # ── Step 2: Transfer flag ────────────────────────────────────────────────
    df = step2_load_transfer(df)

    # ── Step 3: Non-penetrating filter ───────────────────────────────────────
    df = step3_filter_nonpenetrating(df)

    # ── Step 4: Feature engineering ──────────────────────────────────────────
    df = step4_feature_engineering(df)

    # ── Step 5: Sequential exclusions ────────────────────────────────────────
    df = step5_sequential_exclusions(df)

    # Save intermediate file (R: write.csv(tqi13_feb14_nonpenetrating1, ...))
    df.to_csv(OUT_INTERMEDIATE, index=False)
    print(f"\n  Intermediate file saved → {OUT_INTERMEDIATE.name}  "
          f"({len(df):,} rows)")

    # ── Step 5b: Assign treatment group g ────────────────────────────────────
    df = step5b_assign_treatment_group(df)

    # ── Step 6: TQIP inclusion filter ────────────────────────────────────────
    df = step6_tqip_inclusion(df)

    # Save final file
    df.to_csv(OUT_FINAL, index=False)
    print(f"\n  Final file saved → {OUT_FINAL.name}  ({len(df):,} rows)")

    # ── Summary ──────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Pipeline complete")
    print(f"  Intermediate (pre-inclusion): {OUT_INTERMEDIATE.name}")
    print(f"  Final dataset:                {OUT_FINAL.name}")
    if "g" in df.columns:
        print(f"\n  Treatment group distribution (g=1 NOM, 2 Angio, 3 Splenorrhaphy, 4 Splenectomy):")
        print(df["g"].value_counts().sort_index().to_string())
        print(f"  Total: {len(df):,}")
    print("=" * 60)


if __name__ == "__main__":
    main()
