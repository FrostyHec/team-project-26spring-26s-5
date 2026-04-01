

# **Smart Campus Academic Assistant: A Multi-Functional Student Support Platform**

## 1. Project Overview

This project aims to develop a **Smart Campus Academic Assistant** for university students. The system integrates academic reminders, course support, campus policy search, course recommendation, and campus news delivery into one platform. It is designed to reduce students’ information overload and help them better manage academic tasks, understand course materials, keep up with university policies, and explore campus opportunities.

The target users include students at different stages of campus life, such as freshmen, students during course selection periods, and students preparing for final exams. The system will support multiple usage scenarios across the semester and provide personalized assistance based on users’ needs.

------

# Part I. Preliminary Requirement  Analysis

## 2. Functional Requirements

The proposed system contains the following **five distinct and notable features**.

### Feature 1: Deadline Management

The system helps students manage important academic deadlines, especially during the final month of the semester.

Main functions include:

- Collecting deadlines from multiple sources such as email, Blackboard, and course announcements
- Extracting and summarizing due dates for assignments, projects, quizzes, and exams
- Displaying upcoming deadlines in a unified dashboard
- Sending reminders before deadlines
- Allowing users to filter deadlines by course or urgency

### Feature 2: Course Assistant

The system provides course-related support, especially during exam weeks.

Main functions include:

- Interpreting lecture slides and course materials
- Generating concise review notes from uploaded or collected teaching materials
- Supporting exam preparation through key-point summarization
- Generating practice questions based on course content
- Archiving and organizing course materials for later review

### Feature 3: Campus Policy Search

The system allows users, especially freshmen, to search and understand campus policies.

Main functions include:

- Searching policy information from university departments and official websites
- Answering questions about policies such as registration, housing, attendance, leave procedures, and academic regulations
- Providing summarized and readable explanations of official policy documents
- Linking answers back to the original official sources

### Feature 4: Course Recommendation

The system provides course recommendation services during the beginning of the semester.

Main functions include:

- Recommending courses according to user interests, academic background, and degree needs
- Summarizing course descriptions, workload, and possible prerequisites
- Helping students compare multiple courses
- Supporting personalized recommendations based on previous selections or preferences

### Feature 5: Daily Campus News Push

The system provides daily campus news summaries to users through email or public account style delivery.

Main functions include:

- Collecting news from official campus media, public accounts, and department websites
- Summarizing daily campus news into digest form
- Sending personalized news updates via email or other delivery channels
- Highlighting events, opportunities, and announcements relevant to student interests

------

## 3. Non-Functional Requirements

### 3.1 Usability

- The system should be easy to use for students with different technical backgrounds.
- The interface should be clear and intuitive.
- The system should support **multi-platform deployment**, such as web-based access or desktop-based access.
- Core information such as deadlines, recommendations, and news should be presented in a concise and readable way.

### 3.2 Security

- The system should support secure authentication, such as **CAS login** or traditional account-password login.
- User data, including schedules, preferences, and personal information, must be protected from unauthorized access.
- Data transmission should be encrypted where applicable.
- Access to external data sources should be controlled and logged.

### 3.3 Safety

- Potentially risky operations, such as data processing or external tool invocation, should be executed in a **sandboxed environment**.
- The system should avoid generating unsafe or misleading recommendations.
- Official policy and news queries should prioritize trusted sources to reduce misinformation.

### 3.4 Performance

- The system should respond to common user queries within an acceptable delay.
- The daily news push should be **precomputed in advance** to reduce peak-time latency.
- The backend should support **parallel processing** for multi-source data collection and content summarization.
- The system should support **dynamic API routing** to select appropriate services or models efficiently.

### 3.5 Reliability

- The system should remain available during critical academic periods such as course selection and final exam weeks.
- Failures in one external source should not crash the whole system.
- Logs and monitoring should be provided for debugging and maintenance.

### 3.6 Maintainability

- The codebase should be modular so that features can be added or updated independently.
- Data connectors for different campus sources should be easy to extend.
- The system should support iterative development across multiple sprints.

------

## 4. Technical Requirements

### 4.1 Operating Environment

- Development environment: **Linux**
- Deployment environment: Linux server or cloud-based Linux instance
- Access platform: web browser, desktop application (windows or linux)

### 4.2 Tech Stack

- **Frontend:** Vue3 + TypeScript
  Used to build a lightweight and interactive user interface for dashboards, search, and recommendation display.
- **Backend:** LangGraph
  Used to manage multi-step workflows such as data retrieval, summarization, routing, and task coordination.
- **Authentication:** CAS integration or password-based login
  Used to ensure secure access and possible campus identity integration.
- **Data Processing / External APIs:**
  APIs or crawlers for email, Blackboard, official websites, and campus public media accounts.

### 4.3 Execution and Integration Requirements

- The system should integrate multiple heterogeneous data sources.
- The architecture should support modular data pipelines.
- The system should support scheduled tasks for daily news aggregation and reminder generation.
- The backend should be extensible for future integration of recommendation and summarization models.

------

## 5. Data Requirements

The system relies on several categories of data.

### 5.1 Required Data

1. **Academic deadline data**
   Includes assignment deadlines, exam dates, project submissions, and announcement timestamps.
2. **Course material data**
   Includes lecture slides, handouts, archived course files, and review materials.
3. **Campus policy data**
   Includes official regulations, notices, and procedural documents from university departments.
4. **Course information data**
   Includes course catalog descriptions, prerequisites, schedules, and possibly historical student feedback.
5. **Campus news data**
   Includes news, announcements, and event information from university public channels.

### 5.2 Data Sources

- **Email** for email notifications and announcements
- **Blackboard (BB)** for course materials and assignment-related information
- **Official university and departmental websites** for policies and notices
- **APIs or crawlers** for collecting structured or semi-structured data

### 5.3 Data Acquisition

- Through official APIs when available
- Through web scraping or crawling for public campus information
- Through authenticated integration with email and course systems where permission is granted
- Through periodic scheduled retrieval for news and deadline synchronization

### 5.4 Data Challenges

- Different sources may have inconsistent formats
- Some sources may update frequently or unpredictably
- Access control may limit automated retrieval from some platforms
- Data cleaning and deduplication will be necessary before downstream use
