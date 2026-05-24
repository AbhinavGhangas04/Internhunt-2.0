# Resume parsing module for InternHunt
import io
import re
import spacy
import streamlit as st
from pypdf import PdfReader
from spacy.matcher import PhraseMatcher
from thefuzz import process, fuzz
from typing import List, Dict, Any, Optional
from config import Config


@st.cache_resource(show_spinner=False)
def load_spacy_model():
    """Load spaCy model with caching"""
    try:
        return spacy.load("en_core_web_sm")
    except OSError as e:
        st.error("""
        Error loading spaCy model 'en_core_web_sm'. 
        Please install it by running: 
        ```
        python -m spacy download en_core_web_sm
        ```
        and add 'en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1.tar.gz' to your requirements.txt
        """)
        st.error(f"Full error: {str(e)}")
        raise


class ResumeParser:
    """Enhanced resume parser using spaCy and rule-based extraction"""

    def __init__(self):
        self.nlp = self._load_spacy()
        self.valid_skills = self._get_valid_skills()
        self.skill_matcher = self._build_skill_matcher()

    def _load_spacy(self):
        """Load spaCy model, auto-install if missing"""
        return load_spacy_model()

    def _get_valid_skills(self) -> Dict[str, str]:
        """Get comprehensive list of valid skills"""
        skills = {
            # Programming languages
            "python",
            "java",
            "javascript",
            "typescript",
            "c",
            "c++",
            "c#",
            "go",
            "rust",
            "kotlin",
            "swift",
            "ruby",
            "php",
            "r",
            "matlab",
            "scala",
            # Web frameworks
            "html",
            "css",
            "react",
            "next.js",
            "nextjs",
            "angular",
            "vue",
            "svelte",
            "node.js",
            "nodejs",
            "express",
            "django",
            "flask",
            "fastapi",
            "spring",
            "spring boot",
            "laravel",
            "rails",
            # Data/ML/AI
            "pandas",
            "numpy",
            "scikit-learn",
            "sklearn",
            "tensorflow",
            "keras",
            "pytorch",
            "nlp",
            "computer vision",
            "opencv",
            "xgboost",
            "lightgbm",
            "matplotlib",
            "seaborn",
            "plotly",
            # Databases/Cloud/DevOps
            "sql",
            "mysql",
            "postgresql",
            "sqlite",
            "mongodb",
            "redis",
            "elasticsearch",
            "aws",
            "gcp",
            "azure",
            "docker",
            "kubernetes",
            "git",
            "github",
            "gitlab",
            "ci/cd",
            "terraform",
            # Hardware/Electrical
            "verilog",
            "vhdl",
            "systemverilog",
            "fpga",
            "pcb design",
            "circuit design",
            "digital design",
            "analog design",
            "vlsi",
            "asic",
            "embedded systems",
            "arm",
            "msp430",
            "pic",
            "arduino",
            # Mobile
            "android",
            "ios",
            "react native",
            "swiftui",
            "flutter",
            # Testing/Others
            "pytest",
            "jest",
            "cypress",
            "playwright",
            "graphql",
            "rest",
            "grpc",
            "microservices",
        }

        return {skill.lower(): skill for skill in skills}

    def _build_skill_matcher(self):
        """Build spaCy phrase matcher for skills"""
        phrases = list(self.valid_skills.keys())
        patterns = [self.nlp.make_doc(p) for p in phrases]
        matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        matcher.add("SKILL", patterns)
        return matcher

    def read_pdf_text(self, uploaded_file) -> str:
        """Extract raw text from uploaded PDF"""
        try:
            file_bytes = uploaded_file.read()
            reader = PdfReader(io.BytesIO(file_bytes))
            pages = []

            for page in reader.pages:
                try:
                    pages.append(page.extract_text() or "")
                except Exception:
                    pages.append("")

            text = "\n".join(pages)
            # Normalize whitespace
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text.strip()
        except Exception as e:
            st.error(f"Error reading PDF: {e}")
            return ""

    def extract_contact_info(self, text: str) -> Dict[str, Any]:
        """Extract contact information from resume text"""
        email_pattern = re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
        )
        phone_pattern = re.compile(
            r"(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}|\d{5}[\s\-]?\d{5})"
        )
        url_pattern = re.compile(r"\b(?:https?://|www\.)[^\s<>)+]+", re.I)
        github_pattern = re.compile(r"github\.com/[A-Za-z0-9_.\-]+", re.I)
        linkedin_pattern = re.compile(
            r"(?:linkedin\.com/in/|linkedin\.com/pub/)[A-Za-z0-9\-\_/%]+", re.I
        )

        emails = list(dict.fromkeys(email_pattern.findall(text)))
        phones = list(dict.fromkeys(phone_pattern.findall(text)))
        urls = list(dict.fromkeys(url_pattern.findall(text)))
        github = list(dict.fromkeys(github_pattern.findall(text)))
        linkedin = list(dict.fromkeys(linkedin_pattern.findall(text)))

        return {
            "emails": emails,
            "phones": phones,
            "urls": urls,
            "github": github,
            "linkedin": linkedin,
        }

    def extract_skills(self, text: str) -> List[str]:
        """Extract skills using fuzzy matching and NLP"""
        doc = self.nlp(text.lower())
        found_skills = set()

        # Use spaCy matcher
        matches = self.skill_matcher(doc)
        for _, start, end in matches:
            skill = doc[start:end].text.strip().lower()
            if skill in self.valid_skills:
                found_skills.add(self.valid_skills[skill])

        # Fuzzy matching for additional skills
        text_lower = text.lower()
        for skill_key, skill_value in self.valid_skills.items():
            if skill_key.replace("-", " ") in text_lower:
                found_skills.add(skill_value)
            else:
                # Fuzzy match
                result = process.extractOne(
                    skill_key, [text_lower], scorer=fuzz.token_set_ratio
                )
                if result and result[1] >= Config.FUZZY_THRESHOLD:
                    found_skills.add(skill_value)

        return list(found_skills)

    def _first_nonempty_lines(self, text: str, n: int = 5) -> List[str]:
        """Get first n non-empty lines from text"""
        lines = []
        for line in text.split("\n"):
            if line.strip():
                lines.append(line.strip())
                if len(lines) >= n:
                    break
        return lines

    def extract_name(self, text: str) -> Optional[str]:
        """Extract candidate name using improved heuristic approach"""
        # Get first 5 non-empty lines
        top_lines = self._first_nonempty_lines(text, n=5)
        top_text = "\n".join(top_lines)

        # Method 1: Look for name patterns in the first few lines
        name_candidates = []

        # Check first 3 lines for name patterns
        for i, line in enumerate(top_lines[:3]):
            # Skip lines that look like contact info, headers, or URLs
            if self._is_contact_or_header_line(line):
                continue

            # Look for capitalized name patterns
            name = self._extract_name_from_line(line)
            if name and self._is_valid_name(name):
                name_candidates.append((name, i))  # (name, line_index)

        # If we found valid names, return the one from the earliest line
        if name_candidates:
            name_candidates.sort(key=lambda x: x[1])  # Sort by line index
            return name_candidates[0][0]

        # Method 2: Use spaCy NER as fallback, but with better filtering
        top_doc = self.nlp(top_text)
        persons = []
        for ent in top_doc.ents:
            if ent.label_ == "PERSON":
                person_text = ent.text.strip()
                # Filter out obvious non-names
                if self._is_valid_name(person_text) and not self._contains_url_or_email(
                    person_text
                ):
                    persons.append(person_text)

        if persons:
            # Prefer 2-3 word names, then by length
            persons.sort(key=lambda s: (abs(len(s.split()) - 2), -len(s)))
            return persons[0]

        return None

    def _is_contact_or_header_line(self, line: str) -> bool:
        """Check if line contains contact info or headers"""
        line_lower = line.lower()
        contact_indicators = [
            "phone",
            "email",
            "mobile",
            "contact",
            "address",
            "linkedin",
            "github",
            "curriculum vitae",
            "resume",
            "cv",
            "projects",
            "experience",
            "education",
            "skills",
            "objective",
            "summary",
            "profile",
        ]
        return any(indicator in line_lower for indicator in contact_indicators)

    def _extract_name_from_line(self, line: str) -> Optional[str]:
        """Extract potential name from a single line"""
        # Remove common prefixes/suffixes
        line = re.sub(r"^(mr\.?|ms\.?|mrs\.?|dr\.?)\s*", "", line, flags=re.IGNORECASE)

        # Split into tokens and find capitalized words
        tokens = line.split()
        cap_words = []

        for token in tokens:
            # Match capitalized words (allowing for hyphens and apostrophes)
            if re.match(r"^[A-Z][a-zA-Z'\-]+$", token):
                cap_words.append(token)
            else:
                # If we hit a non-capitalized word, stop (names are usually consecutive)
                break

        # Return if we have 2-4 capitalized words
        if 2 <= len(cap_words) <= 4:
            return " ".join(cap_words)

        return None

    def _is_valid_name(self, name: str) -> bool:
        """Validate if extracted text looks like a real person's name"""
        if not name or len(name.strip()) < 2:
            return False

        name = name.strip()
        words = name.split()

        # Must have 2-4 words
        if not (2 <= len(words) <= 4):
            return False

        # Each word should be 2+ characters and start with capital letter
        for word in words:
            if len(word) < 2 or not re.match(r"^[A-Z][a-zA-Z'\-]*$", word):
                return False

        # Check for common non-name patterns
        name_lower = name.lower()
        non_name_patterns = [
            "university",
            "college",
            "institute",
            "company",
            "corporation",
            "inc",
            "ltd",
            "department",
            "school",
            "academy",
            "center",
            "centre",
            "group",
            "team",
            "project",
            "research",
            "development",
            "engineering",
            "technology",
            "science",
            "curriculum",
            "vitae",
            "resume",
            "cv",
            "profile",
            "summary",
            "objective",
            "software",
            "engineer",
            "developer",
            "analyst",
            "manager",
            "director",
            "specialist",
            "consultant",
            "coordinator",
            "administrator",
            "supervisor",
        ]

        if any(pattern in name_lower for pattern in non_name_patterns):
            return False

        # Additional validation: check if it looks like a job title
        job_title_indicators = [
            "engineer",
            "developer",
            "analyst",
            "manager",
            "specialist",
            "consultant",
        ]
        if any(indicator in name_lower for indicator in job_title_indicators):
            return False

        return True

    def _contains_url_or_email(self, text: str) -> bool:
        """Check if text contains URL or email patterns"""
        url_pattern = r"https?://|www\.|\.com|\.org|\.net|\.edu|\.gov"
        email_pattern = r"@"
        return bool(
            re.search(url_pattern, text, re.IGNORECASE)
            or re.search(email_pattern, text)
        )

    def parse_resume(self, uploaded_file) -> Dict[str, Any]:
        """Main parsing function"""
        text = self.read_pdf_text(uploaded_file)
        if not text:
            return {}

        name = self.extract_name(text)
        contacts = self.extract_contact_info(text)
        skills = self.extract_skills(text)

        return {
            "name": name,
            "email": contacts["emails"][0] if contacts["emails"] else None,
            "mobile_number": contacts["phones"][0] if contacts["phones"] else None,
            "skills": skills,
            "linkedin": contacts["linkedin"],
            "github": contacts["github"],
            "raw_text": text,
        }
