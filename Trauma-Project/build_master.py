"""
build_master.py  –  Build master dataset from raw TQIP PUF CSVs
================================================================
Assembles a patient-level master dataframe from ACS TQIP Public Use Files
for 2016 (classic PUF format) and 2024 (new PUF format) admission years.

Output: all_with_comp_from_puf.xlsx in the project root
        → used as input for preprocess.py

Column conventions (matching the original R master dataset):
    INC_KEY             unique patient identifier
    AGE                 patient age
    GENDER              Male / Female / Non-Binary
    RACE1               primary race
    ETHNIC              ethnicity
    ISSAIS              Injury Severity Score (ISS)
    spleenseverity      spleen AIS severity (1–6, from AIS P-code)
    ED_Sbp              ED systolic blood pressure
    ED_PULSE            ED pulse rate
    TRANS_BLOOD_4HOURS  units of blood in first 4 h (raw, binarized in preprocess.py)
    TRANS_PLASMA_4HOURS units of plasma in first 4 h
    TRANS_PLATELETS_4HOURS units of platelets in first 4 h
    TRANSFER            transfer-in status (text)
    EDDISP              ED discharge disposition (text)
    HOSPDISP            hospital discharge disposition (text)
    death1              1 = died in ED, 0 otherwise
    death               1 = died in hospital, 0 otherwise
    comorb{n}           binary comorbidity indicator (n = COMORKEY / condition code)
    compl{n}            binary complication indicator (n = COMPLKEY / event code)
    AY                  admission year (2016, 2024)
"""

from pathlib import Path
import numpy as np
import pandas as pd

# ── Project paths ─────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent

# 2016 source files
D2_2016 = PROJECT_ROOT / "Dataset 2" / "PUF AY 2016" / "CSV"
D3_2016 = PROJECT_ROOT / "Dataset 3" / "PUF AY 2016" / "CSV"
D4_2016 = PROJECT_ROOT / "Dataset 4" / "PUF AY 2016" / "CSV"

# 2024 source files
D2_2024 = PROJECT_ROOT / "Dataset 2" / "PUFAY2024"
D3_2024 = PROJECT_ROOT / "Dataset 3" / "PUFAY2024"
D_LOOKUP = PROJECT_ROOT / "Dataset"  / "PUFAY2024"

OUTPUT_FILE = PROJECT_ROOT / "all_with_comp_from_puf.csv"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read(path: Path, usecols: list[str] | None = None, **kwargs) -> pd.DataFrame:
    # Peek at actual header to map requested column names case-insensitively,
    # since some PUF files use lowercase inc_key while others use INC_KEY.
    if usecols is not None:
        header = pd.read_csv(path, nrows=0, low_memory=False, **kwargs)
        actual = {c.strip().upper(): c for c in header.columns}
        mapped = [actual[u.upper()] for u in usecols if u.upper() in actual]
        missing = [u for u in usecols if u.upper() not in actual]
        if missing:
            raise ValueError(f"{path.name}: columns not found: {missing}")
        df = pd.read_csv(path, usecols=mapped, low_memory=False, **kwargs)
    else:
        df = pd.read_csv(path, low_memory=False, **kwargs)
    df.columns = df.columns.str.strip().str.upper()
    return df


def _pivot_long_to_wide(
    df: pd.DataFrame,
    key_col: str,
    prefix: str,
    positive_only: bool = True,
) -> pd.DataFrame:
    """
    Pivot a long-format indicator table to one binary column per key value.

    For 2016 PUF_COMORBID / PUF_COMPLIC:
        key_col = 'COMORKEY' / 'COMPLKEY'
        positive_only=True  → keep rows where key > 0 (negative = Not Applicable)

    For 2024 PUF_PREEXISTINGCONDITIONS / PUF_HOSPITALEVENTS:
        pass df already filtered to answer==1 (Yes) rows
        positive_only=False (already filtered)

    Returns: one row per INC_KEY, columns '{prefix}{n}' = 1 if patient had
    that condition, 0 otherwise.
    """
    if positive_only:
        df = df[df[key_col] > 0].copy()

    # One row per (INC_KEY, key_col) – de-duplicate
    df = df[["INC_KEY", key_col]].drop_duplicates()
    df[key_col] = df[key_col].astype(int)

    # Pivot: INC_KEY as index, key_col values as columns, fill 0
    wide = (
        df.assign(val=1)
          .pivot_table(index="INC_KEY", columns=key_col, values="val",
                       aggfunc="max", fill_value=0)
    )
    wide.columns = [f"{prefix}{c}" for c in wide.columns]
    wide = wide.reset_index()
    return wide


# ─────────────────────────────────────────────────────────────────────────────
# 2016 builder
# ─────────────────────────────────────────────────────────────────────────────

def build_2016() -> pd.DataFrame:
    print("\n" + "=" * 60)
    print("Building 2016 master")
    print("=" * 60)

    # ── Demographics (base table) ──────────────────────────────────────────
    demo = _read(D4_2016 / "PUF_DEMO.csv")
    demo["INC_KEY"] = pd.to_numeric(demo["INC_KEY"], errors="coerce")
    print(f"  PUF_DEMO       : {len(demo):>8,} patients")

    # ── Spleen AIS severity ───────────────────────────────────────────────
    # PREDOT starting with "44" → spleen; take worst (max) severity per patient
    ais = _read(D3_2016 / "PUF_AISPCODE.csv",
                usecols=["INC_KEY", "PREDOT", "SEVERITY"])
    ais["INC_KEY"]  = pd.to_numeric(ais["INC_KEY"], errors="coerce")
    ais["PREDOT"]   = ais["PREDOT"].astype(str)
    ais["SEVERITY"] = pd.to_numeric(ais["SEVERITY"], errors="coerce")
    spleen_ais = (
        ais[ais["PREDOT"].str.startswith("44")]
        .groupby("INC_KEY", as_index=False)["SEVERITY"]
        .max()
        .rename(columns={"SEVERITY": "spleenseverity"})
    )
    # Exclude severity 9 (unspecified/missing) from usable values
    spleen_ais.loc[spleen_ais["spleenseverity"] == 9, "spleenseverity"] = np.nan
    print(f"  PUF_AISPCODE   : {len(spleen_ais):>8,} patients with spleen AIS")

    # ── ED vitals ─────────────────────────────────────────────────────────
    # Filter VSTYPE=='ED'; keep first ED row per patient
    vitals = _read(D3_2016 / "PUF_VITALS.csv",
                   usecols=["INC_KEY", "VSTYPE", "SBP", "PULSE"])
    vitals["INC_KEY"] = pd.to_numeric(vitals["INC_KEY"], errors="coerce")
    ed_vitals = (
        vitals[vitals["VSTYPE"].str.strip() == "ED"]
        .copy()
    )
    ed_vitals["SBP"]   = pd.to_numeric(ed_vitals["SBP"],   errors="coerce")
    ed_vitals["PULSE"] = pd.to_numeric(ed_vitals["PULSE"], errors="coerce")
    # Replace BIU sentinel values (-1, -2) with NaN
    ed_vitals.loc[ed_vitals["SBP"]   < 0, "SBP"]   = np.nan
    ed_vitals.loc[ed_vitals["PULSE"] < 0, "PULSE"] = np.nan
    ed_vitals = (
        ed_vitals.sort_values("INC_KEY")
                 .drop_duplicates(subset="INC_KEY", keep="first")
                 [["INC_KEY", "SBP", "PULSE"]]
                 .rename(columns={"SBP": "ED_Sbp", "PULSE": "ED_PULSE"})
    )
    print(f"  PUF_VITALS (ED): {len(ed_vitals):>8,} patients with ED vitals")

    # ── Transfusions (PUF_PM) ─────────────────────────────────────────────
    pm = _read(D4_2016 / "PUF_PM.csv",
               usecols=["INC_KEY", "TRANS_BLOOD_4HOURS",
                        "TRANS_PLASMA_4HOURS", "TRANS_PLATELETS_4HOURS"])
    pm["INC_KEY"] = pd.to_numeric(pm["INC_KEY"], errors="coerce")
    for col in ["TRANS_BLOOD_4HOURS", "TRANS_PLASMA_4HOURS", "TRANS_PLATELETS_4HOURS"]:
        pm[col] = pd.to_numeric(pm[col], errors="coerce")
    pm = pm.drop_duplicates(subset="INC_KEY", keep="first")
    print(f"  PUF_PM         : {len(pm):>8,} patients with transfusion data")

    # ── ED encounter: ISSAIS, TRANSFER, EDDISP ────────────────────────────
    ed = _read(D3_2016 / "PUF_ED.csv",
               usecols=["INC_KEY", "ISSAIS", "TRANSFER", "EDDISP"])
    ed["INC_KEY"] = pd.to_numeric(ed["INC_KEY"], errors="coerce")
    ed["ISSAIS"]  = pd.to_numeric(ed["ISSAIS"],  errors="coerce")
    ed.loc[ed["ISSAIS"] < 0, "ISSAIS"] = np.nan
    ed = ed.drop_duplicates(subset="INC_KEY", keep="first")
    print(f"  PUF_ED         : {len(ed):>8,} patients with ED data")

    # ── Discharge: HOSPDISP ───────────────────────────────────────────────
    disch = _read(D3_2016 / "PUF_DISCHARGE.csv",
                  usecols=["INC_KEY", "HOSPDISP", "LOSDAYS", "ICUDAYS"])
    disch["INC_KEY"] = pd.to_numeric(disch["INC_KEY"], errors="coerce")
    disch = disch.drop_duplicates(subset="INC_KEY", keep="first")
    print(f"  PUF_DISCHARGE  : {len(disch):>8,} patients with discharge data")

    # ── Comorbidities (long → wide) ───────────────────────────────────────
    comorb_long = _read(D3_2016 / "PUF_COMORBID.csv",
                        usecols=["INC_KEY", "COMORKEY"])
    comorb_long["INC_KEY"]  = pd.to_numeric(comorb_long["INC_KEY"],  errors="coerce")
    comorb_long["COMORKEY"] = pd.to_numeric(comorb_long["COMORKEY"], errors="coerce")
    comorb_wide = _pivot_long_to_wide(comorb_long, "COMORKEY", "comorb",
                                      positive_only=True)
    print(f"  PUF_COMORBID   : {len(comorb_wide):>8,} patients, "
          f"{len([c for c in comorb_wide.columns if c.startswith('comorb')])} comorbidity cols")

    # ── Complications (long → wide) ───────────────────────────────────────
    complic_long = _read(D3_2016 / "PUF_COMPLIC.csv",
                         usecols=["INC_KEY", "COMPLKEY"])
    complic_long["INC_KEY"]  = pd.to_numeric(complic_long["INC_KEY"],  errors="coerce")
    complic_long["COMPLKEY"] = pd.to_numeric(complic_long["COMPLKEY"], errors="coerce")
    complic_wide = _pivot_long_to_wide(complic_long, "COMPLKEY", "compl",
                                       positive_only=True)
    print(f"  PUF_COMPLIC    : {len(complic_wide):>8,} patients, "
          f"{len([c for c in complic_wide.columns if c.startswith('compl')])} complication cols")

    # ── E-codes (for penetrating injury filter in preprocess.py) ─────────
    ecode = _read(D3_2016 / "PUF_ECODE.csv",
                  usecols=["INC_KEY", "ECODE", "ECODE2"])
    ecode["INC_KEY"] = pd.to_numeric(ecode["INC_KEY"], errors="coerce")
    # Keep one row per patient (primary E-code)
    ecode = ecode.drop_duplicates(subset="INC_KEY", keep="first")
    print(f"  PUF_ECODE      : {len(ecode):>8,} patients with E-code")

    # ── Merge all ─────────────────────────────────────────────────────────
    print("\n  Merging 2016 components...")
    df = demo.copy()
    for right, name in [
        (spleen_ais, "spleen AIS"),
        (ed_vitals,  "ED vitals"),
        (pm,         "PM transfusions"),
        (ed,         "ED encounter"),
        (disch,      "discharge"),
        (comorb_wide,"comorbidities"),
        (complic_wide,"complications"),
        (ecode,      "E-codes"),
    ]:
        df = df.merge(right, on="INC_KEY", how="left")
        print(f"    after {name}: {len(df):,} rows")

    # ── Derived columns ───────────────────────────────────────────────────
    # death1: died in ED (before inpatient admission)
    df["death1"] = (df["EDDISP"].str.strip() == "Deceased/Expired").astype(int)
    # death: in-hospital mortality
    df["death"] = (df["HOSPDISP"].str.strip() == "Deceased/Expired").astype(int)
    df["AY"] = 2016

    # Fill comorbidity/complication columns with 0 for patients not in
    # PUF_COMORBID / PUF_COMPLIC (i.e., they have no recorded conditions)
    comorb_cols  = [c for c in df.columns if c.startswith("comorb")]
    complic_cols = [c for c in df.columns if c.startswith("compl")]
    df[comorb_cols]  = df[comorb_cols].fillna(0).astype(int)
    df[complic_cols] = df[complic_cols].fillna(0).astype(int)

    print(f"\n  2016 master: {df.shape[0]:,} rows × {df.shape[1]} columns")
    print(f"    deaths (in-hosp): {df['death'].sum():,}  |  ED deaths: {df['death1'].sum():,}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 2024 builder
# ─────────────────────────────────────────────────────────────────────────────

def build_2024() -> pd.DataFrame:
    print("\n" + "=" * 60)
    print("Building 2024 master")
    print("=" * 60)

    # ── PUF_TRAUMA.csv (primary wide file: demographics + vitals + outcomes) ──
    trauma = _read(D2_2024 / "PUF_TRAUMA.csv")
    trauma["INC_KEY"] = pd.to_numeric(trauma["INC_KEY"], errors="coerce")
    print(f"  PUF_TRAUMA     : {len(trauma):>8,} patients")

    # Rename 2024 columns to match 2016/R-script conventions
    rename_map = {
        "AGEYEARS":               "AGE",
        "SEX":                    "GENDER_CODE",       # numeric; decoded below
        "SBP":                    "ED_Sbp",
        "PULSERATE":              "ED_PULSE",
        "ISS":                    "ISSAIS",
        "BLOOD4HOURS":            "TRANS_BLOOD_4HOURS",
        "PLASMA4HOURS":           "TRANS_PLASMA_4HOURS",
        "PLATELETS4HOURS":        "TRANS_PLATELETS_4HOURS",
        "INTERFACILITYTRANSFER":  "TRANSFER_CODE",     # numeric; decoded below
        "EDDISCHARGEDISPOSITION": "EDDISP_CODE",       # numeric; decoded below
        "HOSPDISCHARGEDISPOSITION":"HOSPDISP_CODE",    # numeric; decoded below
        "VERIFICATIONLEVEL":      "ADULTVERIFICATIONLEVEL",
        "PRIMARYECODEICD10":      "ECODE_ICD10",       # for injury-type lookup
    }
    trauma = trauma.rename(columns={k: v for k, v in rename_map.items()
                                    if k in trauma.columns})

    # Decode numeric GENDER_CODE → text matching 2016 format
    gender_map = {1: "Male", 2: "Female", 3: "Non-Binary"}
    if "GENDER_CODE" in trauma.columns:
        trauma["GENDER"] = (
            pd.to_numeric(trauma["GENDER_CODE"], errors="coerce")
            .map(gender_map)
        )

    # Decode TRANSFER_CODE: 1=Yes, 2=No
    if "TRANSFER_CODE" in trauma.columns:
        transfer_map = {1: "Yes", 2: "No"}
        trauma["TRANSFER"] = (
            pd.to_numeric(trauma["TRANSFER_CODE"], errors="coerce")
            .map(transfer_map)
            .fillna("Not Known/Not Recorded BIU 2")
        )

    # Decode EDDISP_CODE and HOSPDISP_CODE to text matching 2016
    # 2024 lookup: EdDischargeDisposition 5=Deceased/expired;
    #              HospDischargeDisposition 5=Deceased/Expired
    eddisp_map = {
        1: "Floor bed (general admission, non specialty unit bed)",
        2: "Observation unit (unit that provides < 24 hour stays)",
        3: "Telemetry/step-down unit (less acuity than ICU)",
        4: "Home with services",
        5: "Deceased/Expired",
        6: "Other (jail, institutional care, mental health, etc.)",
        7: "Operating Room",
        8: "Intensive Care Unit (ICU)",
        9: "Home without services",
        10: "Left against medical advice",
        11: "Transferred to another hospital",
    }
    hospdisp_map = {
        1: "Discharged/Transferred to a short-term general hospital for inpatient",
        2: "Discharged/Transferred to an Intermediate Care Facility (ICF)",
        3: "Discharge/Transferred to home under care of organized home health serv",
        4: "Left against medical advice or discontinued care",
        5: "Deceased/Expired",
        6: "Discharged to home or self-care (routine discharge)",
        7: "Discharged/Transferred to Skilled Nursing Facility",
        8: "Discharged/Transferred to hospice care",
        10: "Discharged/Transferred to court/law enforcement",
        11: "Discharged/Transferred to inpatient rehab or designated unit",
        12: "Discharged/Transferred to Long Term Care Hospital",
        13: "Discharged/transferred to a psychiatric hospital or psychiatric distin",
        14: "Discharged/Transferred to another type of institution not defined else",
    }
    if "EDDISP_CODE" in trauma.columns:
        trauma["EDDISP"] = (
            pd.to_numeric(trauma["EDDISP_CODE"], errors="coerce").map(eddisp_map)
        )
    if "HOSPDISP_CODE" in trauma.columns:
        trauma["HOSPDISP"] = (
            pd.to_numeric(trauma["HOSPDISP_CODE"], errors="coerce").map(hospdisp_map)
        )

    # Convert vitals: replace BIU sentinel codes with NaN
    for col in ["ED_Sbp", "ED_PULSE"]:
        if col in trauma.columns:
            trauma[col] = pd.to_numeric(trauma[col], errors="coerce")
            trauma.loc[trauma[col] < 0, col] = np.nan

    # ── Spleen AIS severity ────────────────────────────────────────────────
    ais2024 = _read(D3_2024 / "PUF_AISDIAGNOSIS.csv",
                    usecols=["INC_KEY", "AISPREDOT", "AISSEVERITY"])
    ais2024["INC_KEY"]     = pd.to_numeric(ais2024["INC_KEY"],     errors="coerce")
    ais2024["AISPREDOT"]   = ais2024["AISPREDOT"].astype(str)
    ais2024["AISSEVERITY"] = pd.to_numeric(ais2024["AISSEVERITY"], errors="coerce")
    spleen_2024 = (
        ais2024[ais2024["AISPREDOT"].str.startswith("44")]
        .groupby("INC_KEY", as_index=False)["AISSEVERITY"]
        .max()
        .rename(columns={"AISSEVERITY": "spleenseverity"})
    )
    spleen_2024.loc[spleen_2024["spleenseverity"] == 9, "spleenseverity"] = np.nan
    print(f"  PUF_AISDIAGNOSIS: {len(spleen_2024):>7,} patients with spleen AIS")

    # ── Comorbidities (long → wide) ────────────────────────────────────────
    # PREEXISTINGCONDITIONANSWER: 1=Yes, 2=No  → keep only Yes rows
    cond = _read(D_LOOKUP / "PUF_PREEXISTINGCONDITIONS.csv",
                 usecols=["INC_KEY", "PREEXISTINGCONDITION",
                          "PREEXISTINGCONDITIONANSWER"])
    cond["INC_KEY"] = pd.to_numeric(cond["INC_KEY"], errors="coerce")
    cond["PREEXISTINGCONDITION"]       = pd.to_numeric(cond["PREEXISTINGCONDITION"],       errors="coerce")
    cond["PREEXISTINGCONDITIONANSWER"] = pd.to_numeric(cond["PREEXISTINGCONDITIONANSWER"], errors="coerce")
    cond_yes = cond[cond["PREEXISTINGCONDITIONANSWER"] == 1][["INC_KEY", "PREEXISTINGCONDITION"]].copy()
    cond_yes = cond_yes.rename(columns={"PREEXISTINGCONDITION": "COMORKEY"})
    comorb_wide = _pivot_long_to_wide(cond_yes, "COMORKEY", "comorb",
                                      positive_only=False)
    print(f"  PREEXISTING CONDS: {len(comorb_wide):>7,} patients, "
          f"{len([c for c in comorb_wide.columns if c.startswith('comorb')])} comorbidity cols")

    # ── Complications (long → wide) ────────────────────────────────────────
    # HOSPITALEVENTANSWER: 1=Yes, 2=No → keep only Yes rows
    events = _read(D2_2024 / "PUF_HOSPITALEVENTS.csv",
                   usecols=["INC_KEY", "HOSPITALEVENT", "HOSPITALEVENTANSWER"])
    events["INC_KEY"]              = pd.to_numeric(events["INC_KEY"],              errors="coerce")
    events["HOSPITALEVENT"]        = pd.to_numeric(events["HOSPITALEVENT"],        errors="coerce")
    events["HOSPITALEVENTANSWER"]  = pd.to_numeric(events["HOSPITALEVENTANSWER"],  errors="coerce")
    events_yes = events[events["HOSPITALEVENTANSWER"] == 1][["INC_KEY", "HOSPITALEVENT"]].copy()
    events_yes = events_yes.rename(columns={"HOSPITALEVENT": "COMPLKEY"})
    complic_wide = _pivot_long_to_wide(events_yes, "COMPLKEY", "compl",
                                       positive_only=False)
    print(f"  HOSPITAL EVENTS : {len(complic_wide):>7,} patients, "
          f"{len([c for c in complic_wide.columns if c.startswith('compl')])} complication cols")

    # ── Injury type from ICD-10 E-code lookup ─────────────────────────────
    # TRAUMATYPE: 1=Blunt, 2=Penetrating, 3=Burn, 4=Other/Unspecified
    ecode_lookup = _read(D_LOOKUP / "PUF_ECODE_LOOKUP.csv",
                         usecols=["ECODE", "TRAUMATYPE"])
    ecode_lookup["ECODE"]      = ecode_lookup["ECODE"].astype(str).str.strip()
    ecode_lookup["TRAUMATYPE"] = pd.to_numeric(ecode_lookup["TRAUMATYPE"], errors="coerce")
    # Drop rows where TRAUMATYPE is missing (lookup rows for other purposes)
    ecode_lookup = ecode_lookup.dropna(subset=["TRAUMATYPE"])

    # Map TRAUMATYPE code → text for consistency with 2016 INJTYPE
    traumatype_map = {1: "Blunt", 2: "Penetrating", 3: "Burn", 4: "Other/Unspecified"}
    ecode_lookup["INJTYPE"] = ecode_lookup["TRAUMATYPE"].map(traumatype_map)
    ecode_lookup = ecode_lookup[["ECODE", "INJTYPE"]].drop_duplicates(subset="ECODE")

    if "ECODE_ICD10" in trauma.columns:
        trauma["ECODE_ICD10_CLEAN"] = trauma["ECODE_ICD10"].astype(str).str.strip()
        trauma = trauma.merge(
            ecode_lookup.rename(columns={"ECODE": "ECODE_ICD10_CLEAN"}),
            on="ECODE_ICD10_CLEAN", how="left"
        )
        trauma = trauma.rename(columns={"ECODE_ICD10": "ECODE"})
        trauma.drop(columns=["ECODE_ICD10_CLEAN"], inplace=True, errors="ignore")

    # ── Merge all 2024 components ─────────────────────────────────────────
    print("\n  Merging 2024 components...")
    df = trauma.copy()
    for right, name in [
        (spleen_2024,  "spleen AIS"),
        (comorb_wide,  "comorbidities"),
        (complic_wide, "complications"),
    ]:
        df = df.merge(right, on="INC_KEY", how="left")
        print(f"    after {name}: {len(df):,} rows")

    # ── Derived columns ───────────────────────────────────────────────────
    df["death1"] = (df["EDDISP"].str.strip() == "Deceased/Expired").astype(int)
    df["death"]  = (df["HOSPDISP"].str.strip() == "Deceased/Expired").astype(int)
    df["AY"] = 2024

    comorb_cols  = [c for c in df.columns if c.startswith("comorb")]
    complic_cols = [c for c in df.columns if c.startswith("compl")]
    df[comorb_cols]  = df[comorb_cols].fillna(0).astype(int)
    df[complic_cols] = df[complic_cols].fillna(0).astype(int)

    print(f"\n  2024 master: {df.shape[0]:,} rows × {df.shape[1]} columns")
    print(f"    deaths (in-hosp): {df['death'].sum():,}  |  ED deaths: {df['death1'].sum():,}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("TQIP Master Dataset Builder")
    print("=" * 60)

    df_2016 = build_2016()
    df_2024 = build_2024()

    # ── Align comorbidity / complication columns across years ─────────────
    # Ensure both DataFrames have the same comorb/compl columns (fill 0 if absent)
    all_cols = sorted(set(df_2016.columns) | set(df_2024.columns))
    indicator_cols = [c for c in all_cols if c.startswith("comorb") or c.startswith("compl")]
    for col in indicator_cols:
        if col not in df_2016.columns:
            df_2016[col] = 0
        if col not in df_2024.columns:
            df_2024[col] = 0

    # ── Concatenate ───────────────────────────────────────────────────────
    print("\n── Combining 2016 + 2024 ──")
    master = pd.concat([df_2016, df_2024], ignore_index=True, sort=False)
    print(f"  Combined: {master.shape[0]:,} rows × {master.shape[1]} columns")

    # ── Save as CSV (dataset is too large for Excel's 1,048,576 row limit) ──
    print(f"\n  Saving → {OUTPUT_FILE.name} ...")
    master.to_csv(OUTPUT_FILE, index=False)
    print(f"  Saved.  File size: {OUTPUT_FILE.stat().st_size / 1e6:.1f} MB")

    # ── Summary ───────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Master dataset summary")
    print("=" * 60)
    print(f"  Total patients : {len(master):,}")
    print(f"  Columns        : {master.shape[1]}")
    print(f"  Patients with spleenseverity : {master['spleenseverity'].notna().sum():,}")
    print(f"  Patients with ISSAIS         : {master['ISSAIS'].notna().sum():,}")
    print(f"  Patients with ED_Sbp         : {master['ED_Sbp'].notna().sum():,}")
    print(f"  Patients with ED_PULSE       : {master['ED_PULSE'].notna().sum():,}")
    print(f"\n  Rows per year:")
    print(master["AY"].value_counts().sort_index().to_string())
    print(f"\n  death (in-hospital): {master['death'].sum():,}  "
          f"({master['death'].mean()*100:.1f}%)")
    print(f"  death1 (ED deaths) : {master['death1'].sum():,}  "
          f"({master['death1'].mean()*100:.1f}%)")

    comorb_cols  = sorted([c for c in master.columns if c.startswith("comorb")])
    complic_cols = sorted([c for c in master.columns if c.startswith("compl")])
    print(f"\n  Comorbidity columns ({len(comorb_cols)}): {comorb_cols}")
    print(f"\n  Complication columns ({len(complic_cols)}): {complic_cols}")

    print(f"\n  All columns:\n  {list(master.columns)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
