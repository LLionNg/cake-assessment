import os

import pandas as pd
import streamlit as st

from src.core.config import load_settings
from src.services.matcher import KOLMatcher
from src.utils.log import setup_logging

st.set_page_config(page_title="TikTok KOL Matcher", layout="wide")


@st.cache_resource
def get_matcher() -> KOLMatcher:
    settings = load_settings(os.getenv("KOL_CONFIG", "config.yml"))
    setup_logging(settings.log_level)
    return KOLMatcher(settings)


matcher = get_matcher()

st.title("TikTok KOL Matcher")
st.caption(f"Mode: {matcher.services.mode}. Set mock in config.yml to switch to mock data.")

with st.form("inputs"):
    facebook_url = st.text_input("Facebook page URL", "https://www.facebook.com/example")
    website_url = st.text_input("Website URL (optional)")
    limits = matcher.settings.matching
    top_n = st.slider(
        "Number of KOLs", 1, limits.max_candidates, min(limits.top_n, limits.max_candidates)
    )
    submitted = st.form_submit_button("Find KOLs", type="primary")

if submitted:
    with st.spinner("Profiling brand, discovering creators, scoring matches..."):
        try:
            report = matcher.run(facebook_url, website_url or None, top_n)
        except RuntimeError as e:
            st.error(str(e))
            st.stop()

    brand = report.brand
    st.subheader(f"{brand.brand_name} - {brand.industry}")
    st.write(brand.summary)
    left, right = st.columns(2)
    left.markdown(f"**Target audience:** {brand.target_audience}")
    left.markdown(f"**Content style:** {brand.content_style}")
    left.markdown(f"**Preferred tiers:** {', '.join(map(str, sorted(brand.preferred_tiers)))}")
    right.markdown(f"**Search queries:** {', '.join(brand.search_queries)}")
    right.markdown(f"**Hashtags:** {' '.join('#' + h for h in brand.hashtags)}")

    st.subheader(f"Top {len(report.matches)} recommended KOLs")
    if not report.matches:
        st.warning(
            "No Thai creators matched. Try a different page or relax the filters in config.yml."
        )
    else:
        df = pd.DataFrame([m.to_row() for m in report.matches])
        st.dataframe(
            df,
            hide_index=True,
            width="stretch",
            column_config={
                "profile": st.column_config.LinkColumn(
                    "Profile", display_text=r"https://www\.tiktok\.com/(@.*)"
                ),
                "score": st.column_config.ProgressColumn("Score", min_value=0, max_value=1),
                "engagement_rate": st.column_config.NumberColumn("ER", format="percent"),
            },
        )
        st.download_button(
            "Download CSV", df.to_csv(index=False), "kol_matches.csv", "text/csv", on_click="ignore"
        )
        st.download_button(
            "Download JSON",
            report.model_dump_json(indent=2),
            "kol_matches.json",
            "application/json",
            on_click="ignore",
        )
