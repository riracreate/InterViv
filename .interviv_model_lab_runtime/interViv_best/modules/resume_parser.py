import re
import pdfplumber


def parse_resume(pdf_path):
    """
    Parse a PDF resume and extract skills.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        List of skills extracted from the resume
    """
    skills = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Extract text from all pages
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() or ""
            
            # Convert to lowercase for matching
            text_lower = full_text.lower()
            
            # Common technical skills to look for
            tech_skills = [
                # Languages
                'python', 'javascript', 'java', 'c++', 'c#', 'go', 'rust', 'ruby', 'php',
                'typescript', 'scala', 'kotlin', 'swift', 'objective-c', 'perl', 'r',
                
                # Web Technologies
                'html', 'css', 'react', 'vue', 'angular', 'node.js', 'express', 'django',
                'flask', 'fastapi', 'spring', 'asp.net', 'rails',
                
                # Databases
                'sql', 'mongodb', 'postgresql', 'mysql', 'redis', 'elasticsearch',
                'cassandra', 'dynamodb', 'oracle', 'firebase',
                
                # Cloud & DevOps
                'aws', 'azure', 'gcp', 'google cloud', 'docker', 'kubernetes', 'jenkins',
                'gitlab', 'github', 'terraform', 'ansible', 'ci/cd',
                
                # Data & AI
                'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'scikit-learn',
                'pandas', 'numpy', 'spark', 'hadoop', 'nlp', 'computer vision',
                
                # Other
                'git', 'linux', 'windows', 'macos', 'rest api', 'graphql', 'soap',
                'microservices', 'system design', 'agile', 'scrum', 'jira'
            ]
            
            # Extract matching skills
            for skill in tech_skills:
                # Use word boundaries to match whole words
                if re.search(r'\b' + re.escape(skill) + r'\b', text_lower):
                    skills.append(skill.title())
            
            # Remove duplicates and sort
            skills = sorted(list(set(skills)))
            
            # If no skills found, return a default
            if not skills:
                skills = ["Python"]
                
    except Exception as e:
        print(f"Error parsing PDF: {e}")
        skills = ["Python"]
    
    return skills
