#!/usr/bin/env python3
"""
InternHunt - Resume Analyzer Application
A comprehensive resume analysis tool with job recommendations and skill assessment.
"""

# Core libraries
import streamlit as st
import pandas as pd
import base64
import random
import time
import datetime
import os
import nltk

# Load Streamlit Cloud secrets into the environment before config/database init
_SECRET_KEYS = (
    'DB_TYPE', 'DB_HOST', 'DB_PORT', 'DB_USER', 'DB_PASSWORD', 'DB_NAME',
    'JOOBLE_API_KEY', 'ADZUNA_APP_ID', 'ADZUNA_API_KEY', 'ADZUNA_COUNTRY',
    'OLLAMA_HOST', 'OLLAMA_MODEL', 'CA_CERT_PATH',
)


def _hydrate_streamlit_secrets():
    try:
        for key in _SECRET_KEYS:
            if key in st.secrets:
                os.environ.setdefault(key, str(st.secrets[key]))
    except Exception:
        pass


_hydrate_streamlit_secrets()

# Import custom modules
from config import Config
from database import DatabaseManager
db_manager = DatabaseManager()
from api_services import JobAPIService
from resume_parser import ResumeParser
from styles import StyleManager
from utils import AnalyticsUtils
from chat_service import chat_ollama, build_resume_context, check_ollama_health, get_suggested_questions
from streamlit.components.v1 import html as st_html  # legacy; floating chat removed
from job_scrapers import scrape_all
from Courses import ds_course, web_course, android_course, ios_course, uiux_course

# -----------------------------
# Application Setup
# -----------------------------

def initialize_app():
    """Initialize the Streamlit application"""
    # Validate configuration
    config_status = Config.validate_config()
    if not config_status['valid']:
        st.error("Configuration issues found:")
        for issue in config_status['issues']:
            st.error(f"- {issue}")
        st.stop()
    
    # Set page config
    st.set_page_config(
        page_title=Config.APP_TITLE,
        page_icon=Config.APP_ICON,
        layout="wide",
    )
    
    # Initialize theme
    if "theme_mode" not in st.session_state:
        st.session_state.theme_mode = "dark"
    
    # Ensure NLTK data only once per session
    if not st.session_state.get("nltk_ready"):
        nltk.download('stopwords', quiet=True)
        nltk.download('punkt', quiet=True)
        nltk.download('wordnet', quiet=True)
        nltk.download('averaged_perceptron_tagger', quiet=True)
        st.session_state["nltk_ready"] = True
    
    # Apply styles
    StyleManager.apply_global_styles()
    StyleManager.apply_theme_styles(st.session_state.theme_mode)
    # Sidebar chat styles (message bubbles)
    st.markdown(
        """
        <style>
        .sb-chat-title {font-weight: 700; font-size: 18px; margin-bottom: 8px;}
        .sb-chip {display:inline-block; padding:6px 10px; border-radius:999px; font-size:12px; margin-right:6px; background:rgba(255,255,255,0.06);}
        .msg-wrap {max-height: 58vh; overflow-y: auto; padding-right: 4px;}
        .msg {margin: 6px 0; padding: 10px 12px; border-radius: 10px; line-height: 1.35;}
        .msg-user {background: rgba(56,68,255,0.18); border: 1px solid rgba(56,68,255,0.35);} 
        .msg-assist {background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.08);} 
        .msg-role {font-size: 11px; opacity: 0.7; margin-bottom: 4px;}
        .stButton > button,
        div[data-testid="stButton"] > button,
        section[data-testid="stSidebar"] div[data-testid="stButton"] > button {
            background-color: #3b82f6 !important;
            color: #ffffff !important;
            border: 1px solid #2563eb !important;
            border-radius: 8px !important;
        }
        .stButton > button:hover,
        div[data-testid="stButton"] > button:hover,
        section[data-testid="stSidebar"] div[data-testid="stButton"] > button:hover {
            background-color: #2563eb !important;
            color: #ffffff !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

@st.cache_resource(show_spinner=False)
def get_resume_parser():
    """Get cached resume parser instance"""
    return ResumeParser()

def display_header():
    """Display application header"""
    # Theme toggle
    theme = st.toggle("🌙 Dark Mode" if st.session_state.theme_mode == "light" else "☀️ Light Mode")
    st.session_state.theme_mode = "light" if theme else "dark"
    StyleManager.apply_theme_styles(st.session_state.theme_mode)
    
    # Main header
    st.markdown("""
        <div style="text-align: center; margin-bottom: 2rem;">
            <h1 style="font-size: 3em; margin-bottom: 0.2rem;">InternHunt</h1>
            <h3 style="color: #ccc; margin-top: 0;">Resume Analyzer</h3>
            <p style="color: #aaa; font-size: 1.1em;">
                Upload your resume and get smart internship recommendations based on your skills.
            </p>
        </div>
    """, unsafe_allow_html=True)

def get_table_download_link(df, filename, text):
    """Generate download link for dataframe"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'
    return href

def show_pdf(file_path):
    """Display PDF in Streamlit"""
    if not os.path.exists(file_path):
        st.error("PDF file not found.")
        return
    
    try:
        with open(file_path, "rb") as f:
            base64_pdf = base64.b64encode(f.read()).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="700" height="1000" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error displaying PDF: {e}")

def categorize_skills(skills):
    """Categorize skills into different domains"""
    categories = {
        "Technical Skills": [],
        "Hardware/Electrical Engineering": [],
        "Soft Skills": [],
        "Data Science/Analytics": [],
        "Design/Creative": [],
        "Business/Management": [],
        "Other": []
    }
    
    skill_categories = {
        'python': "Technical Skills", 'java': "Technical Skills", 'javascript': "Technical Skills",
        'verilog': "Hardware/Electrical Engineering", 'fpga': "Hardware/Electrical Engineering",
        'communication': "Soft Skills", 'leadership': "Soft Skills",
        'machine learning': "Data Science/Analytics", 'data analysis': "Data Science/Analytics",
        'figma': "Design/Creative", 'photoshop': "Design/Creative",
        'project management': "Business/Management", 'marketing': "Business/Management"
    }
    
    for skill in skills:
        category = skill_categories.get(skill.lower(), "Other")
        categories[category].append(skill)
    
    return {k: v for k, v in categories.items() if v}

def display_skills(categorized_skills):
    """Display categorized skills with styling"""
    st.markdown(StyleManager.get_skills_styles(), unsafe_allow_html=True)
    
    st.markdown("""
        <div class="skills-header">
            <div class="skills-header-icon">🛠️</div>
            <h2 class="skills-header-text">SKILLS EXTRACTED</h2>
        </div>
    """, unsafe_allow_html=True)
    
    category_icons = {
        "Technical Skills": "💻",
        "Hardware/Electrical Engineering": "🔌",
        "Soft Skills": "🤝",
        "Data Science/Analytics": "📊",
        "Design/Creative": "🎨",
        "Business/Management": "📋",
        "Other": "🔧"
    }
    
    css_class_map = {
        "Technical Skills": "tech-skill",
        "Hardware/Electrical Engineering": "hardware-skill",
        "Soft Skills": "soft-skill",
        "Data Science/Analytics": "data-skill",
        "Other": "other-skill"
    }
    
    html_output = '<div class="skills-container">'
    
    for category, skills in categorized_skills.items():
        if skills:
            icon = category_icons.get(category, "✨")
            css_class = css_class_map.get(category, "tech-skill")
            
            html_output += f'''
            <div class="skill-section">
                <h3 class="skill-category">
                    <span class="category-icon">{icon}</span> {category}
                </h3>
                <div class="skills-grid">
            '''
            
            for skill in skills:
                html_output += f'<span class="skill-tag {css_class}">{skill}</span>'
            
            html_output += '</div></div>'
    
    html_output += '</div>'
    st.markdown(html_output, unsafe_allow_html=True)

def _fetch_all_jobs(skills, user_location):
    """Fetch and merge Jooble + scraper jobs into a common schema and deduplicate by URL."""
    jooble_jobs = JobAPIService.fetch_jobs_from_jooble(skills, user_location) or []
    scraped_jobs = scrape_all(skills, user_location) or []

    def map_jooble(j):
        return {
            "title": j.get("title", ""),
            "company": j.get("company", ""),
            "location": j.get("location", "") or "Remote",
            "tags": [],
            "description": j.get("snippet", ""),
            "url": j.get("link", "#"),
            "source": "jooble",
        }

    def map_scraper(j):
        return {
            "title": j.get("title", ""),
            "company": j.get("company", ""),
            "location": j.get("location", "") or "Remote",
            "tags": j.get("tags", []),
            "description": j.get("description", ""),
            "url": j.get("url", "#"),
            "source": j.get("source", "scraper"),
        }

    merged = [map_jooble(j) for j in jooble_jobs] + [map_scraper(j) for j in scraped_jobs]

    # Deduplicate by URL
    seen = set()
    unique = []
    for j in merged:
        u = j.get("url")
        if not u or u in seen:
            continue
        seen.add(u)
        unique.append(j)
    return unique

def _filter_jobs(jobs, query, source):
    """Client-side filter by source and free-text query over multiple fields."""
    q = (query or "").strip().lower()
    s = (source or "All").lower()
    def keep(j):
        js = j.get("source", "").lower()
        if s == "jooble":
            if js != "jooble":
                return False
        elif s == "scrapers":
            # Treat any non-jooble as a scraper
            if js == "jooble":
                return False
        # else: s == all -> no source filter
        if not q:
            return True
        # Prefer matching location first; many scrapers use 'Remote'
        loc = (j.get("location", "") or "").lower()
        if q in loc:
            return True
        # Consider 'remote' a match if user typed something like 'remote'
        if q in ("remote", "wfh", "work from home") and ("remote" in loc or loc == ""):
            return True
        # Otherwise, perform a soft match against title/company/tags/description
        blob = " ".join([
            j.get("title", ""),
            j.get("company", ""),
            " ".join(j.get("tags", [])),
            j.get("description", ""),
        ]).lower()
        return q in blob
    return [j for j in (jobs or []) if keep(j)]

def display_job_recommendations_unified(skills, location):
    """Display unified job recommendations (Jooble + Scrapers) with filters."""
    st.markdown(StyleManager.get_job_listing_styles(), unsafe_allow_html=True)
    st.markdown(StyleManager.get_animation_styles(), unsafe_allow_html=True)

    st.markdown(
        """
        <div class="animated-header" style="
            background-color: #111827;
            padding: 1.2rem;
            border-radius: 8px;
            margin-top: 2rem;
            margin-bottom: 1rem;
        ">
            <h1 style='color: #ffffff; margin: 0;'>💼 Job Recommendations</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Filters row
    c1, c2, c3 = st.columns([4, 2, 1])
    with c1:
        location_query = st.text_input(
            "City/Country or keyword",
            value=location or "",
            placeholder="e.g., Bengaluru, India, Remote",
        )
    with c2:
        source_filter = st.selectbox("Source", ["All", "Jooble", "Scrapers"], index=0)
    with c3:
        fetch = st.button("Fetch jobs")

    # Cache merged results by skills+location
    cache_key = (tuple((skills or [])[:50]), (location_query or "").strip())
    if fetch or st.session_state.get("jobs_cache_key") != cache_key:
        with st.spinner("Fetching jobs..."):
            jobs_all = _fetch_all_jobs(skills, location_query)
        st.session_state["jobs_cache_key"] = cache_key
        st.session_state["jobs_cache"] = jobs_all
    else:
        jobs_all = st.session_state.get("jobs_cache", [])

    # Apply filters
    jobs_filtered = _filter_jobs(jobs_all, location_query, source_filter)

    jooble_count = sum(1 for j in jobs_filtered if j.get("source") == "jooble")
    scraper_count = sum(1 for j in jobs_filtered if j.get("source") != "jooble")
    st.markdown(
        f"""
        <div style=\"background:#0f172a; border:1px solid #1f2937; border-radius:10px; padding:10px 12px; margin: 6px 0 14px 0; color:#e5e7eb;\">\
            Showing <b>{len(jobs_filtered)}</b> results • Jooble: {jooble_count} • Scrapers: {scraper_count}\
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not jobs_filtered:
        st.info("No jobs found. Try clearing filters or using broader location/keywords.")
        return

    for idx, job in enumerate(jobs_filtered):
        display_job_card(job, job.get("source", "scraper"))
        if idx < len(jobs_filtered) - 1:
            st.markdown('<div class="separator"></div>', unsafe_allow_html=True)

def display_job_recommendations(skills, location):
    """Display job recommendations from multiple APIs"""
    st.markdown(StyleManager.get_job_listing_styles(), unsafe_allow_html=True)
    st.markdown(StyleManager.get_animation_styles(), unsafe_allow_html=True)
    
    st.markdown("""
        <div class="animated-header" style="
            background-color: #111827;
            padding: 1.2rem;
            border-radius: 8px;
            margin-top: 2rem;
            margin-bottom: 2rem;
        ">
            <h1 style='color: #ffffff; margin: 0;'>💼 Job Recommendations</h1>
        </div>
    """, unsafe_allow_html=True)
    
    # Jooble jobs
    st.markdown("""
        <div class="animated-header" style="
            background-color: #1e1e1e;
            padding: 0.8rem;
            border-left: 6px solid #60a5fa;
            border-radius: 6px;
            margin-top: 2rem;
            margin-bottom: 1rem;
        ">
            <h2 style='color: #ffffff; margin: 0;'>From Jooble</h2>
        </div>
    """, unsafe_allow_html=True)
    
    jooble_jobs = JobAPIService.fetch_jobs_from_jooble(skills, location)
    
    if jooble_jobs:
        for i, job in enumerate(jooble_jobs):
            display_job_card(job, "jooble")
            if i < len(jooble_jobs) - 1:
                st.markdown('<div class="separator"></div>', unsafe_allow_html=True)
    else:
        st.warning(f"⚠ No jobs found from Jooble in `{location or 'Remote'}`.")

    # Removed Remotive provider section per request

def display_job_card(job, source):
    """Display individual job card"""
    if source == "adzuna":
        job_title = job.get("title", "No Title")
        company_name = job.get("company", {}).get("display_name", "Unknown Company")
        job_location = job.get("location", {}).get("display_name", "Location Not Available")
        job_link = job.get("redirect_url", "#")
        description = job.get("description", "")
    elif source == "jooble":  # jooble
        job_title = job.get("title", "No Title")
        company_name = job.get("company", "Unknown Company")
        job_location = job.get("location", "Location Not Available")
        job_link = job.get("link", "#")
        description = job.get("snippet", "")
    else:  # generic mapping for any future providers
        job_title = job.get("title", "No Title")
        company_name = job.get("company", "Unknown Company")
        job_location = job.get("location", "Remote")
        job_link = job.get("url", "#")
        description = job.get("description", "")
    
    st.markdown('<div class="job-listing">', unsafe_allow_html=True)
    source_name = (source or "").capitalize()
    badge = f"<span style='font-size:11px; padding:3px 8px; border:1px solid #374151; border-radius:999px; color:#9ca3af; background:rgba(255,255,255,0.04); margin-left:8px;'>{source_name}</span>"
    st.markdown(f"<div class=\"job-title\">🔹 {job_title} {badge}</div>", unsafe_allow_html=True)
    
    st.markdown('<div class="job-info-container">', unsafe_allow_html=True)
    st.markdown('<div class="job-info">', unsafe_allow_html=True)
    
    # Company info
    st.markdown(f'''
    <div class="info-item">
        <span>🏢</span>
        <span class="info-label">Company:</span>
        <span>{company_name}</span>
    </div>
    ''', unsafe_allow_html=True)
    
    # Location info
    st.markdown(f'''
    <div class="info-item">
        <span>📍</span>
        <span class="info-label">Location:</span>
        <span>{job_location}</span>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Apply button
    st.markdown(f'''
    <div>
        <a href="{job_link}" target="_blank" style="text-decoration: none;">
            <div class="apply-button">Apply Now</div>
        </a>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Description
    if description:
        desc_short = description[:300] + "..." if len(description) > 300 else description
        st.markdown(f'''
        <div class="info-item" style="align-items: flex-start;">
            <span class="info-label">About this role:</span>
        </div>
        <div style="color: #CCCCCC; margin-top: 10px; padding: 10px; background-color: rgba(33, 33, 33, 0.4); border-radius: 4px;">
            {desc_short}
        </div>
        ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

def course_recommender(course_list):
    """Display course recommendations"""
    st.markdown("""
        <div style="background-color: #0f172a; padding: 15px 25px; border-radius: 12px; 
                    box-shadow: 0 0 15px #3b82f6; color: #e0f2fe; text-align: center; 
                    font-size: 28px; font-weight: bold; margin: 20px 0;">
            Courses & Certificates Recommendations 🎓
        </div>
        <p style='color:#cbd5e1; text-align:center;'>✨ These handpicked courses will boost your skillset and career potential.</p>
    """, unsafe_allow_html=True)
    
    if not course_list:
        st.warning("No course recommendations available at the moment.")
        return []
    
    no_of_reco = st.selectbox(
        "🎯 Select how many recommendations you want to explore:",
        options=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        index=4
    )
    
    recommended_courses = random.sample(course_list, min(no_of_reco, len(course_list)))
    cols = st.columns(2)
    
    for idx, (c_name, c_link) in enumerate(recommended_courses):
        with cols[idx % 2]:
            st.markdown(f"""
                <div style="background: linear-gradient(145deg, #1a1a1a, #232323); padding: 20px; 
                           border-radius: 16px; margin-bottom: 20px; border: 1px solid #2e2e2e; 
                           box-shadow: 0 0 10px rgba(0, 255, 255, 0.2); transition: all 0.3s ease-in-out;">
                    <a href="{c_link}" target="_blank" style="color: #00eaff; text-decoration: none;">
                        <h4>✅ {c_name}</h4>
                        <p style="color: #bcbcbc; font-size: 13px; margin-top: 8px;">🔗 Tap to explore this course</p>
                    </a>
                </div>
            """, unsafe_allow_html=True)
    
    return [c_name for c_name, _ in recommended_courses]

def main():
    """Main application function"""
    initialize_app()
    display_header()
    
    # Public deployment mode: always user flow
    choice = "User"
    st.sidebar.markdown("---")
                        
    st.sidebar.markdown("""
        <p style='text-align: center; font-size: 12px;'>
            © Developed by
            <a href='https://www.linkedin.com/in/abhinav-ghangas-5a3b8128a' target='_blank'>Abhinav</a>
        </p>
    """, unsafe_allow_html=True)
    
    if choice == 'User':
        # File upload section
        st.markdown("""
            <div style="background-color: #1e1e30; padding: 30px; border-radius: 12px; 
                       border: 1px solid #3e3e50; margin-bottom: 25px; max-width: 700px; 
                       margin-left: auto; margin-right: auto; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);">
                <div style="font-size: 24px; font-weight: 700; color: #ffffff; 
                          padding-bottom: 12px; border-bottom: 1px solid #444; margin-bottom: 20px;">
                    Upload Your Resume
                </div>
                <p style="color: #888; font-size: 14px;">Supported format: PDF</p>
            </div>
        """, unsafe_allow_html=True)
        
        pdf_file = st.file_uploader("Upload Resume", type=["pdf"], label_visibility="collapsed")
        
        if pdf_file is not None:
            with st.spinner("Uploading and analyzing your resume..."):
                time.sleep(1)
            
            # Save uploaded file
            save_path = os.path.join(Config.UPLOAD_DIR, pdf_file.name)
            os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
            
            with open(save_path, "wb") as f:
                f.write(pdf_file.getbuffer())
            
            # Track current resume to reset chat state if needed
            try:
                current_resume_id = f"{save_path}:{os.path.getsize(save_path)}"
            except Exception:
                current_resume_id = save_path
            if st.session_state.get('resume_id') != current_resume_id:
                # New file uploaded: parse and cache
                parser = get_resume_parser()
                resume_data = parser.parse_resume(pdf_file)
                st.session_state['resume_id'] = current_resume_id
                st.session_state['resume_data'] = resume_data
                st.session_state['chat_messages'] = []
            else:
                # Use cached parsed resume
                resume_data = st.session_state.get('resume_data')
            
            if resume_data:
                # Display candidate info
                st.markdown(f"""
                <div style="background-color: #1e1e2d; border-radius: 10px; padding: 24px; 
                           margin-bottom: 30px; border: 1px solid rgba(255, 255, 255, 0.08); 
                           box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); max-width: 500px;">
                    <div style="font-size: 24px; font-weight: 700; color: #ffffff; margin-bottom: 18px;">
                        Hello {resume_data.get('name', 'there')}!
                    </div>
                    <div style="color: rgba(255, 255, 255, 0.6); font-size: 13px; margin-bottom: 4px;">
                        EMAIL ADDRESS
                    </div>
                    <div style="color: #ffffff; font-size: 15px; padding: 6px 12px; 
                               background-color: rgba(255, 255, 255, 0.05); border-radius: 6px; 
                               border-left: 3px solid #6e8efb; margin-bottom: 15px;">
                        {resume_data.get('email', 'N/A')}
                    </div>
                    <div style="color: rgba(255, 255, 255, 0.6); font-size: 13px; margin-bottom: 4px;">
                        PHONE NUMBER
                    </div>
                    <div style="color: #ffffff; font-size: 15px; padding: 6px 12px; 
                               background-color: rgba(255, 255, 255, 0.05); border-radius: 6px; 
                               border-left: 3px solid #6e8efb;">
                        {resume_data.get('mobile_number', 'N/A')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Compute and display resume score with breakdown
                breakdown = AnalyticsUtils.calculate_resume_score_breakdown(resume_data)
                score = breakdown["total"]
                components = breakdown["components"]
                suggestions = breakdown.get("suggestions", [])

                with st.container():
                    st.markdown(
                        """
                        <div style="background-color: #0f172a; padding: 12px 18px; border-radius: 10px; border: 1px solid #1f2937; display: inline-block; margin-bottom: 12px;">
                            <div style="color:#9ca3af; font-size:12px;">Resume Score</div>
                            <div style="color:#fff; font-size:22px; font-weight:700;">{}/100</div>
                        </div>
                        """.format(score),
                        unsafe_allow_html=True,
                    )
                    st.progress(score/100)

                with st.expander("Why this score?"):
                    max_map = {"basic_info": 15, "skills": 30, "sections": 25, "achievements": 15, "recency": 10, "links": 5}
                    cols = st.columns(2)
                    for i, key in enumerate(["basic_info", "skills", "sections", "achievements", "recency", "links"]):
                        if key in components:
                            val = components[key]
                            with cols[i % 2]:
                                st.write(f"{key.replace('_', ' ').title()}: {val}/{max_map.get(key, 0)}")
                                denom = max_map.get(key, 1)
                                st.progress(min(float(val)/float(denom), 1.0))

                if suggestions:
                    st.markdown("### Suggestions to improve your resume")
                    for s in suggestions:
                        st.markdown(f"- {s}")

                # Display skills
                skills = resume_data.get('skills', [])
                if skills:
                    categorized_skills = categorize_skills(skills)
                    display_skills(categorized_skills)
                
                # Cache resume context for chat so first turn has context
                try:
                    st.session_state['resume_context'] = build_resume_context(resume_data)
                except Exception:
                    st.session_state['resume_context'] = None

                # Defer chat rendering to bottom of page
                st.session_state['render_chat_at_bottom'] = True
                
                
                # Job search
                col1, col2 = st.columns([6, 1])
                with col1:
                    location_input = st.text_input("", placeholder="Enter your Preferred Location (Leave blank for remote jobs)", key="search_location")
                with col2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    search_button = st.button(" Search")
                
                # Display unified job recommendations (Jooble + Scrapers)
                if skills:
                    display_job_recommendations_unified(skills, location_input)
                
                # Course recommendations
                course_list = []
                if any(skill.lower() in ['python', 'pandas', 'numpy', 'machine learning', 'data analysis'] for skill in skills):
                    course_list.extend(ds_course)
                if any(skill.lower() in ['html', 'css', 'javascript', 'react'] for skill in skills):
                    course_list.extend(web_course)
                if any(skill.lower() in ['kotlin', 'java', 'android'] for skill in skills):
                    course_list.extend(android_course)
                if any(skill.lower() in ['swift', 'ios'] for skill in skills):
                    course_list.extend(ios_course)
                if any(skill.lower() in ['figma', 'ui/ux', 'prototyping'] for skill in skills):
                    course_list.extend(uiux_course)
                
                if course_list:
                    recommended_courses = course_recommender(course_list)
                
                # Save to database
                if resume_data.get('name') and resume_data.get('email'):
                    timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
                    db_manager.insert_user_data(
                        name=resume_data['name'],
                        email=resume_data['email'],
                        res_score=score,
                        timestamp=timestamp,
                        no_of_pages=1,  # Default
                        reco_field="General",
                        cand_level="Intermediate",
                        skills=skills,
                        recommended_skills=[],
                        courses=recommended_courses if 'recommended_courses' in locals() else []
                    )

                # Render chat at the very bottom
                if st.session_state.get('render_chat_at_bottom'):
                    st.markdown(StyleManager.get_chat_styles(), unsafe_allow_html=True)
                    st.markdown("""
                        <div class="chat-container">
                            <div class="chat-header">
                                <div class="chat-title">
                                    <div class="chat-avatar">🤖</div>
                                    <span>InternHunt Assistant</span>
                                </div>
                                <div class="chat-status">
                                    <div class="status-dot"></div>
                                    <span>Online</span>
                                </div>
                            </div>
                    """, unsafe_allow_html=True)

                    st.markdown("""
                        <div class="chat-controls">
                            <div class="control-group">
                                <span class="control-label">Style:</span>
                    """, unsafe_allow_html=True)

                    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                    with col1:
                        chat_style = st.selectbox("", ["Concise", "Detailed", "Short"], index=0, key="chat_style", label_visibility="collapsed")
                    with col2:
                        st.session_state['chat_use_context'] = st.checkbox("Use resume context", value=True, key="chat_use_ctx")
                    with col3:
                        if st.button("🗑️ Clear", key="chat_clear", help="Clear chat history"):
                            st.session_state['chat_messages'] = []
                            st.toast("Chat cleared!")
                            st.rerun()
                    with col4:
                        if st.button("🔥 Warm", key="chat_warm", help="Warm up the model"):
                            with st.spinner("Warming up model..."):
                                try:
                                    health = check_ollama_health()
                                    if health['status'] == 'healthy':
                                        _ = chat_ollama([{ "role": "user", "content": "Hello"}], None, "Respond with 'Ready to help!'")
                                        st.success("Model warmed up! 🚀")
                                    else:
                                        st.error(f"Ollama not ready: {health.get('error', 'Unknown error')}")
                                except Exception as e:
                                    st.error(f"Failed to warm up: {e}")

                    st.markdown("</div></div>", unsafe_allow_html=True)

                    health = check_ollama_health()
                    if health['status'] != 'healthy':
                        st.error(f"⚠️ Ollama connection issue: {health.get('error', 'Unknown error')}")
                        st.info("Make sure Ollama is running: `ollama serve`")
                    elif not health.get('model_exists', False):
                        st.warning(f"⚠️ Model '{health['model']}' not found. Available models: {', '.join(health.get('available_models', []))}")

                    if 'chat_messages' not in st.session_state or not st.session_state['chat_messages']:
                        suggested_questions = get_suggested_questions(resume_data)
                        if suggested_questions:
                            st.markdown("""
                                <div class="suggested-questions">
                                    <h4>💡 Try asking:</h4>
                                    <div class="question-chips">
                            """, unsafe_allow_html=True)
                            cols = st.columns(2)
                            for i, question in enumerate(suggested_questions[:6]):
                                with cols[i % 2]:
                                    if st.button(f"💬 {question}", key=f"suggest_{i}", help="Click to ask this question"):
                                        st.session_state['suggested_question'] = question
                                        st.rerun()
                            st.markdown("</div></div>", unsafe_allow_html=True)

                    if 'suggested_question' in st.session_state:
                        user_text = st.session_state['suggested_question']
                        del st.session_state['suggested_question']
                    else:
                        user_text = None

                    if 'chat_messages' not in st.session_state:
                        st.session_state['chat_messages'] = []
                    for m in st.session_state['chat_messages'][-50:]:
                        role = m.get('role', 'user')
                        content = m.get('content', '') or ''
                        timestamp = m.get('timestamp', '')
                        if role == 'user':
                            st.markdown(f"""
                                <div class="message-container message-user">
                                    <div class="message-bubble user">{content}</div>
                                    <div class="message-time">{timestamp}</div>
                                </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                                <div class="message-container message-assistant">
                                    <div class="message-bubble assistant">{content}</div>
                                    <div class="message-time">{timestamp}</div>
                                </div>
                            """, unsafe_allow_html=True)

                    if user_text is None:
                        with st.form("chat_form", clear_on_submit=True):
                            c_in1, c_in2 = st.columns([10, 1])
                            with c_in1:
                                user_text_value = st.text_input("", placeholder="Ask me anything about your resume, career, or job search...", key="chat_text_input")
                            with c_in2:
                                send = st.form_submit_button("➤")
                        if send and (user_text_value or "").strip():
                            user_text = (user_text_value or "").strip()
                    if user_text:
                        timestamp = datetime.datetime.now().strftime("%H:%M")
                        st.session_state['chat_messages'].append({
                            "role": "user",
                            "content": user_text,
                            "timestamp": timestamp
                        })
                        typing_placeholder = st.empty()
                        typing_placeholder.markdown("""
                            <div class="typing-indicator">
                                <span>InternHunt Assistant is typing</span>
                                <div class="typing-dots">
                                    <div class="typing-dot"></div>
                                    <div class="typing-dot"></div>
                                    <div class="typing-dot"></div>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        context = st.session_state.get('resume_context') if st.session_state.get('chat_use_context', True) else None
                        if chat_style == "Concise":
                            sys = "You are InternHunt Assistant. Be concise and practical. Use short bullet points and emojis sparingly."
                        elif chat_style == "Detailed":
                            sys = "You are InternHunt Assistant. Provide detailed bullet points with 1-line rationale for each. Be comprehensive but organized."
                        else:
                            sys = "You are InternHunt Assistant. Answer in 2-3 short sentences, directly addressing the user's request. Be friendly and encouraging."
                        try:
                            reply = chat_ollama(st.session_state['chat_messages'], resume_context=context, system_prompt=sys)
                            typing_placeholder.empty()
                            st.session_state['chat_messages'].append({
                                "role": "assistant",
                                "content": reply,
                                "timestamp": datetime.datetime.now().strftime("%H:%M")
                            })
                            st.rerun()
                        except Exception as e:
                            typing_placeholder.empty()
                            error_msg = f"Sorry, I encountered an error: {str(e)}. Please try again."
                            st.session_state['chat_messages'].append({
                                "role": "assistant",
                                "content": error_msg,
                                "timestamp": datetime.datetime.now().strftime("%H:%M")
                            })
                            st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.error("Could not parse the resume. Please ensure it's a valid PDF with text content.")
    
    elif choice == 'Admin':
        st.subheader(" Admin Dashboard")
        
        # Display user data
        user_data = db_manager.get_user_data(50)
        if user_data:
            df = pd.DataFrame(user_data, columns=[
                'ID', 'Name', 'Email', 'Resume Score', 'Timestamp', 'Pages',
                'Predicted Field', 'User Level', 'Skills', 'Recommended Skills', 'Courses'
            ])
            st.dataframe(df)
            
            # Download link
            st.markdown(
                get_table_download_link(df, "user_data.csv", " Download Data as CSV"),
                unsafe_allow_html=True
            )
        else:
            st.info("No user data available.")

if __name__ == "__main__":
    main()