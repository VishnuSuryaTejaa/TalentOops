import requests
import base64

resume_text = """
John Doe
john.doe@example.com
123-456-7890

SUMMARY
A software engineer with experience in building web applications.

SKILLS
Python, FastAPI, React, Node.js

EXPERIENCE
Software Engineer at TechCorp (2020 - 2023)
- Developed a highly scalable microservices architecture.

PROJECTS
1. E-Commerce Platform
Built a full-stack e-commerce site using React and FastAPI. Integrated Stripe for payments.
Technologies: React, FastAPI, Stripe
Link: github.com/johndoe/ecommerce

2. Personal Blog
A static blog built with Next.js and TailwindCSS.
Technologies: Next.js, TailwindCSS, Markdown
Link: johndoe.com

EDUCATION
B.S. in Computer Science
University of Technology, 2020
"""

encoded = base64.b64encode(resume_text.encode('utf-8')).decode('utf-8')

response = requests.post(
    "http://127.0.0.1:8000/upload_resume",
    json={"file_name": "test_resume.txt", "content": encoded}
)

print(response.status_code)
print(response.json())
