import pandas as pd
import re
import numpy as np
import os

def slugify(s):
    s = s.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    return re.sub(r"[\s_]+", "-", s).strip("-")

try:
    # 1) Load curriculum CSV
    curr_path = r"Curriculum/Maths/curriculum_08052026_small_steps.csv"
    df = pd.read_csv(curr_path, encoding="utf-8")

    # Column name mapping check: we use 'year' instead of 'year_group'
    # 2) Repair numbering anomaly
    df.loc[df["small_step_num"] >= 1142, "small_step_num"] -= 4

    # 3) Ensure Similarity block has 4 rows at global 1135..1138
    mask = (df["year"] == "Year 9") & (df["term"] == "Spring") & (df["macro_topic"] == "Similarity")
    
    # Template from 1135
    template_row = df[df["small_step_num"] == 1135]
    if template_row.empty:
        # fallback to mask
        template = df[mask].iloc[0].to_dict()
    else:
        template = template_row.iloc[0].to_dict()
    
    new_names = [
        "Recognise enlargement and similarity",
        "Work out unknown lengths and angles in similar shapes",
        "Solve problems with similar triangles E",
        "Ratio in right-angled triangles E"
    ]
    
    # Separate rows not in the 1135..1138 range
    # Note: 1138 might exist, but we will overwrite it with our new logic.
    before = df[df["small_step_num"] < 1135].copy()
    after = df[df["small_step_num"] > 1138].copy()
    
    similarity_block = []
    
    # Try to get existing desc/wr_desc for 1-3
    def get_val(num, col, default):
        r = df[df["small_step_num"] == num]
        if not r.empty: return r.iloc[0][col]
        return default

    ss_wr_descs = [
        get_val(1135, "ss_wr_desc", ""),
        get_val(1136, "ss_wr_desc", ""),
        get_val(1137, "ss_wr_desc", ""),
        "In this extend step, before the formal study of trigonometry later in the year, students explore the ratios of side lengths in right-angled triangles, building on their previous understanding of ratios in similar triangles.Define and explain the terms “hypotenuse”, “adjacent” and “opposite”. Start with right-angled triangles with interior anglesof 30° and 60°. Encourage students to label the sides correctlyand then to explore the relationships between these sides asdecimals, fractions or ratios. They should compare the ratioswith similar triangles, discussing the patterns that they observe. They use the ratios to calculate unknown side lengths and angles in similar triangles. Once students are confident,they could extend their exploration to ratios in other right-angled triangles."
    ]
    ss_descs = [
        get_val(1135, "ss_desc", ""),
        get_val(1136, "ss_desc", ""),
        get_val(1137, "ss_desc", ""),
        "Explore ratios of side lengths in right-angled triangles and identify hypotenuse, adjacent, and opposite sides."
    ]

    for i in range(4):
        num = 1135 + i
        itp = i + 1
        name = new_names[i]
        
        row = template.copy()
        row["small_step_num"] = num
        row["small_step_num_in_topic"] = itp
        row["legacy_step_position"] = itp
        row["topic"] = "Similarity"
        row["unique_row"] = "Year9SpringSimilarity"
        row["small_step_name"] = name
        row["ss_wr_desc"] = ss_wr_descs[i]
        row["ss_desc"] = ss_descs[i]
        
        # 4) Regenerate IDs/keys
        row["small_step_id"] = f"Year 9_13-14_Spring__Similarity_{itp}_{name}"
        slug = slugify(name)
        row["small_step_key"] = f"year-9__13-14__spring__blank__similarity__{itp}__{slug}"
        
        similarity_block.append(row)

    df_sim = pd.DataFrame(similarity_block)
    df = pd.concat([before, df_sim, after]).sort_values("small_step_num").reset_index(drop=True)

    # 5) Save curriculum
    df.to_csv(curr_path, index=False, encoding="utf-8")
    canonical_sim = df[df["small_step_num"].isin([1135, 1136, 1137, 1138])].copy()

    # 6) Canonical sync in BOTH precomputed files
    precomp_files = ["precomputed_recommendations_flat.csv", "precomputed_recommendations_flat"]
    for pf in precomp_files:
        if os.path.exists(pf):
            pdf = pd.read_csv(pf, encoding="utf-8")
            if "small_step_num_global" in pdf.columns:
                # First, we need to handle the global decrement in precomputed files too?
                # The prompt says: "Canonical sync... for rows where small_step_num_global in 1135..1138"
                # It doesn't explicitly say repair global numbering in precomputed, but it says "for row 1142+" 
                # "Repair numbering anomaly by decrementing small_step_num by 4 for every row with small_step_num >= 1142" 
                # was directed at curriculum. However, usually these files must match.
                # Let's apply the same decrement to precomputed global nums to maintain consistency.
                pdf.loc[pdf["small_step_num_global"] >= 1142, "small_step_num_global"] -= 4
                
                for _, c_row in canonical_sim.iterrows():
                    g_num = c_row["small_step_num"]
                    mask = pdf["small_step_num_global"] == g_num
                    
                    pdf.loc[mask, "topic"] = c_row["topic"]
                    pdf.loc[mask, "small_step_num"] = c_row["small_step_num_in_topic"]
                    pdf.loc[mask, "small_step_num_in_topic"] = c_row["small_step_num_in_topic"]
                    pdf.loc[mask, "small_step"] = c_row["small_step_name"]
                    pdf.loc[mask, "small_step_name"] = c_row["small_step_name"]
                    pdf.loc[mask, "small_step_desc"] = c_row["ss_desc"]
                    pdf.loc[mask, "ss_wr_desc"] = c_row["ss_wr_desc"]
                    pdf.loc[mask, "small_step_id"] = c_row["small_step_id"]
                    pdf.loc[mask, "small_step_key"] = c_row["small_step_key"]
                    
                    if "recommendation_num" in pdf.columns:
                        # Rebuild recommendation_id
                        # We use a masking approach to apply the function only to relevant rows
                        pdf.loc[mask, "recommendation_id"] = pdf.loc[mask].apply(
                            lambda r: f"{c_row['small_step_id']}_recommendation_{int(float(r['recommendation_num']))}" if pd.notnull(r['recommendation_num']) and str(r['recommendation_num']).replace('.','',1).isdigit() else r["recommendation_id"],
                            axis=1
                        )
                pdf.to_csv(pf, index=False, encoding="utf-8")

    # 7) Constraints file
    const_path = r"Improve_pick\constraints_gate.csv"
    if os.path.exists(const_path):
        cdf = pd.read_csv(const_path, encoding="utf-8")
        id_prefixes = ("Year 9_13-14_Spring__Recognise enlargement and similarity_", "Year 9_13-14_Spring__Similarity_")
        cdf_filtered = cdf[~cdf["small_step_id"].str.startswith(id_prefixes, na=False)].copy()
        
        new_const_rows = []
        for _, c_row in canonical_sim.iterrows():
            new_row = {col: "" for col in cdf.columns}
            new_row["not_aligned"] = 0
            for col in cdf.columns:
                if col in c_row: new_row[col] = c_row[col]
            new_const_rows.append(new_row)
            
        cdf_final = pd.concat([cdf_filtered, pd.DataFrame(new_const_rows)], ignore_index=True)
        cdf_final = cdf_final[cdf.columns]
        cdf_final.to_csv(const_path, index=False, encoding="utf-8")

    # 8) Verification
    print("A) Curriculum 1135..1140:")
    print(df[df["small_step_num"].between(1135, 1140)][["small_step_num", "small_step_num_in_topic", "topic", "small_step_name", "small_step_id"]].to_string())
    print("\nB) Numbering Audit:")
    print(f"Row count: {len(df)}")
    print(f"Min: {df['small_step_num'].min()}, Max: {df['small_step_num'].max()}")
    all_nums = set(range(int(df['small_step_num'].min()), int(df['small_step_num'].max()) + 1))
    missing = sorted(list(all_nums - set(df['small_step_num'])))
    print(f"Missing count: {len(missing)}")
    if missing: print(f"First 10 missing: {missing[:10]}")

    for pf in ["precomputed_recommendations_flat.csv", "precomputed_recommendations_flat"]:
        if os.path.exists(pf):
            print(f"\nC) Verification for {pf}:")
            pdf = pd.read_csv(pf)
            subset = pdf[pdf["small_step_num_global"].between(1135, 1138)]
            if not subset.empty:
                print(subset[["small_step_num_global", "topic", "small_step_num", "small_step_name", "small_step_id"]].drop_duplicates().sort_values("small_step_num_global").to_string())
                print("Counts by global:")
                print(subset["small_step_num_global"].value_counts().sort_index())

    if os.path.exists(const_path):
        print("\nD) Constraints Verification:")
        cdf = pd.read_csv(const_path)
        c_subset = cdf[cdf["small_step_id"].str.startswith("Year 9_13-14_Spring__Similarity_", na=False)]
        print(c_subset[["small_step_id"]].to_string())
        print(f"Count: {len(c_subset)}")

except Exception as e:
    import traceback
    print(f"ERROR: {e}")
    traceback.print_exc()

