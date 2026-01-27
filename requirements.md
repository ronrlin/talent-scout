requirements.md

# Overview

Build Talent Scout, a system to scout and research job opportunities that are well suited for me.  

Scout should be able to compile lists of prospective companies to work for, conduct searches for open or recently posted job opportunities at these companies, identify the jobs that are most suitable given my experience and preferences, compose brief cold emails to use for contacting people at these companies to seek out referrals, compose cover letters to submit with my applications and most importantly, to customize my resume to be as aligned with teh job description as possible -- given my work experiences and skills.

## Agents and Agent Skills

The following agent sub-skills are needed to achieve the goals of the Talent Scout system: 

### Company Scout Agent
Company Scout understands what kinds of roles I'm looking, the geographies I'm looking for, and builds and prioritizes these companies.  It publishes this list to three files -- companies-boca.txt, companies-palo.txt and companies-remote.txt. 

### Company Researcher Agent
Company Researcher conducts individual investigations into a company.  Implement a GET route that allows you to invoke the agent, passing a company name as a parameter.  It should use Claude to look up material information about a company, such as recent news, recent financial performance and filings, company mission and most importantly -- recent job openings.  

Each job opening should be assigned a unique identifier.  The agent should publish a list jobs-boca.txt, jobs-palo.txt and jobs-remote.txt.  Each file should contain a list containing: job identifier, url, company name 

### Connection Finder Agent
ConnectionFinder looks for connections at specific companies, to help support a cold outreach program to find a role or apply for a job.  It uses my LinkedIn profile.  

### Job Researcher and Resume Agent
Job Researcher understands a specific job description, including job requirements, experience required. 
Using this information, build a customized resume that aligns to the job requirements and overall needs of the company. 

Customized resumes should be output as PDFs with a standardized naming convention -- "Ron Lin Resume - {company name}.pdf".  The cover letter should be output as a PDF with standard naming convention -- "Cover Letter {company name}.pdf"

# My Base Resume

My base resume can be used as the source material to build "custom" resumes for each job application I submit.  

# Geographic Requirements 

- My first priority is to identify compelling job opportunities that allow me to relocate to Boca Raton, Florida
- I prefer in-person roles in Boca Raton or southern Florida
- However, finding good jobs in southern florida may be difficult and I currently live in Palo Alto, CA.  
- Palo Alto is a hub for world-class tech jobs.
- My second priority is to find great job opportunities in or near Palo Alto
- I prefer in-person roles in Palo Alto and expect higher compensation
- My third priority are to find great remote opportunities that allow me to move to Boca Raton
- I am willing to compromise on compensation and on other desirable qualities i find in job prospects for a remote job 

# Desirable Job Targets

- I value working for technology companies.  
- I value working for companies where software is a revenue driver, not a cost center
- I value working for companies where software is an essential part of the business, not a means to an end
- My target cash compensation is $300,000 per year
- My target total compensation for a Silicon Valley tech job would be $500,000 per year
- I recognize that I may need to accept lower compensation in order to have a remote job or a "desirable" job in Boca Raton, Florida
- I have experience as a software manager, engineering manager, and I would be interested in exploring roles as a Technical Product Manager


Read the plan I have in requirements.md, then interview me using AskUserQuestionTool to refine and improve the requirements for Talent Scout.  Publish a revised and improved plan as PRD.md.