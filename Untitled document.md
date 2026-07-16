HENALYTICS: A PREDICTIVE ANALYTICS SYSTEM FOR POULTRY EGG PRODUCTION, SALES FORECASTING, AND HEN LAYING PERFORMANCE IN CLSU  
A Capstone Project  
Presented to the  
Department of Information Technology  
In Partial Fulfillment  
of the Requirements for the Degree  
BACHELOR OF SCIENCE IN INFORMATION TECHNOLOGY  
By:  
Dandan, Sharlin P.  
Quinol, Gabriel Nicholas  
Santos, Dina S.  
April 2026  
Department of Information Technology  
COLLEGE OF ENGINEERING  
CENTRAL LUZON STATE UNIVERSITY  
Science City of Muñoz, Nueva Ecija  
ii  
DISCLAIMER  
“This Capstone Project is submitted to the Department of Information Technology, College of Engineering, in partial fulfillment of the requirements for the degree Bachelor of Science in Information Technology at the Central Luzon State University, Science City of Muñoz, Nueva Ecija. It is a product of our own work except were indicated in the text. The project report or any portion thereof including the source code, or any section may be freely copied and distributed provided that the source is acknowledged.”  
iii  
APPROVAL SHEET  
This capstone project proposal, entitled “HENALYTICS: A PREDICTIVE ANALYTICS SYSTEM FOR POULTRY EGG PRODUCTION, SALES FORECASTING, AND HEN LAYING PERFORMANCE IN CLSU” prepared and submitted by SHARLIN PALOMO DANDAN, GABRIEL NICHOLAS QUINOL, DINA SUBA SANTOS in partial fulfillment of the requirements for the degree BACHELOR OF SCIENCE IN INFORMATION TECHNOLOGY, has been examined and is hereby endorsed.  
KARLO CRIS G. BOLISAY  
Adviser  
CAPSTONE 1 PROJECT ORAL PRESENTATION COMMITTEE  
IVAN CHRISTIAN L. SALINAS  
MARY CAMILLE D. RABANG  
Chair  
Member  
Date Signed  
Date Signed  
Accepted and approved in partial fulfillment of the requirements for the degree BACHELOR OF SCIENCE IN INFORMATION TECHNOLOGY, school year 2024-2025.  
DR. KHAVEE AGUSTUS W. BOTANGEN  
Head, Department of Information Technology  
\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_  
Date Signed  
DR. ROY SEARCA JOSE P. DELA CRUZ  
Dean, College of Engineering  
\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_  
Date Signed  
iv  
ABSTRACT  
The poultry sector is a crucial factor in food security and economic sustainability, especially in egg production. To ensure productivity and profitability, the production of eggs, sales, and performance of laying hens should be managed effectively. Nonetheless, most poultry businesses struggle with the analysis of past data and effective prediction of the egg production because most of the traditional methods are not automated, flexible, and data driven. In the CLSU Poultry Module I, the monitoring of egg production and sales is still based on traditional and manual methods, which restrict effective data analysis and decision-making.  
In response to these challenges, this study aims to develop a Predictive Analytics System integrated with automated egg counting using IoT to reduce manual labor and improve efficiency. Using machine learning models such as Regression Analysis and time series models like ARIMA, the system can learn from historical data to generate more accurate predictions on egg production, sales trends, and performance of laying hens. The system will include record management, sales management, and flock management modules, as well as visual analytics modules and will also be able to produce reports which can be easily downloaded and give real time information to facilitate quick and improved decision making in the poultry facility.  
This system is anticipated to improve monitoring and forecasting, as well as offer better visualization of production and sales trends, enabling users to get concrete information based on historical data, which will assist in better management of egg production operations.  
v  
TABLE OF CONTENTS  
TITLE PAGE i  
DISCLAIMER ii  
APPROVAL SHEET iii  
ABSTRACT iv  
TABLE OF CONTENTS v  
CHAPTER 1 1  
INTRODUCTION 1  
Background of the Study 1  
Company Client/Profile 5  
STATEMENT OF THE PROBLEM 6  
General Problem 6  
Specific Problem 7  
OBJECTIVES 7  
General Objective 8  
Specific Objectives 8  
SCOPE AND LIMITATION 8  
Scope 8  
Limitations 10  
SIGNIFICANCE OF THE STUDY 11  
Students 11  
Faculty and Staff 11  
University Offices 11  
Public and External Users 11  
Future Researchers 11  
Future Developers 11  
Relation to Sustainable Development Goals 11  
DEFINITIONS OF TERMS 12  
CHAPTER 2 15  
REVIEW OF RELATED LITERATURE AND EXISTING ALTERNATIVES 15  
Introduction 15  
Previous Studies and Findings 15  
Existing Alternatives 18  
Gaps in Existing Research 21  
vi  
Synthesis 24  
CHAPTER 3 26  
METHODOLOGY 26  
Conceptual Framework 26  
Feasibility Study 27  
Requirements 30  
Profile of Respondents and Selection Methods 32  
Data Gathering Procedure 33  
Ethical Considerations 35  
Design 35  
Development 40  
Developmental Tools and Techniques 40  
Testing 42  
Deployment 42  
Review 43  
REFERENCES 49  
APPENDICES 57  
Appendix A. System Architecture Diagram 57  
Appendix B. Use Case Diagram 58  
Appendix C. Data Flow Diagram 59  
Appendix D. Unified Modeling Language 60  
Appendix E. Entity Relationship Diagram 61  
Appendix F. Flow Chart Diagram 62  
Appendix G. Proposed Prototype 69  
vii  
LIST OF FIGURES  
Figure No. Title Page  
1 Agile Methodology (Jayathilaka, 2020\) . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 27  
2 System Architecture. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 57  
3 Use Case Diagram. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 58  
4 Data Processing and Predictive Modelling. . . . . . . . . . . . . . . . . . . . . . . . . . 59  
5 Image Processing and Object Detection . . . . . . . . . . . . . . . . . . . . . . . . . . . . 59  
6 Unified Modeling Language. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 60  
7 Entity Relationship Diagram. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 61  
8 Flowchart Diagram. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 62  
LIST OF TABLES  
Table No. Title Page  
1 Gaps in Existing Research. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 22  
2 Minimum Specifications. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 28  
3 Recommended Specifications. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 29  
4 Quality Characteristics of ISO/IEC 25010\. . . . . . . . . . . . . . . . . . . . . . . . . 44  
5 User Acceptance Testing (UAT)……………….. . . . . . . . . . . . . . . . . . . . . . 46  
6 Likert Evaluation Scale. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 47  
7 auth\_user . . . . . . . . .. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 63  
8 UserProfile . . . . . . . . . . . . . . . .. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 63  
9 Flock . . . .. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 63  
10 ProductionLog. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 64  
11 GradingLog. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 65  
12 SalesTransaction . . . . . .. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 66  
13 SalesItem. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 66  
14 ModelVersion. . . . . . . . . . .. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 66  
15 HarvestForecast. . . . . . . . . . .. . . . . . . . . .. . . . . . . . . . . . . . . . . . . . . . . . . . . 67  
16 SalesForecast. . . . . . . . . . .. . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . . 68  

Aligned Model-to-Table Mapping for the Implemented System  
The current Django implementation uses UserProfile, Flock, ProductionLog, GradingLog, SalesTransaction, SalesItem, ModelVersion, HarvestForecast, and SalesForecast. The earlier names “PoultryProduction Record,” “EggGradingRecord,” and “EggSales Transaction” should therefore be revised to ProductionLog, GradingLog, and SalesTransaction respectively.  

1  
CHAPTER I  
INTRODUCTION  
Background of the Study  
The poultry industry is a fundamental pillar of global food systems, supporting nutrition, economic stability, and livelihood worldwide (Nassar, 2025). One of the primary products of poultry farming is eggs, which serves as an important source of protein, and affordable food in the global market. Farrelly Mitchell (Food & Agribusiness Specialist, 2025\) reported that the global poultry industry continues to experience pressure to increase operational efficiency, minimize costs, and improve animal welfare. However, despite its importance, several challenges continue to affect the operation and management of poultry production.  
According to Kulyk et al. (2025), one of the primary issues is the limited ability to forecast changes in the chicken population and production, resulting in inefficient use of resources such as feed, space, and labor, as well as unstable supply. In relation to this, Alfirdaus et al. (2025) reported that the poultry supply chain also encounters inconsistent production levels, and limited transparency in information flow, which causes low operational efficiency and negative impact on the welfare of farmers. Similarly, Putra et al. (2024) highlighted that the chicken egg production in different regions in Indonesia indicates substantial changes over time. Garcia-Arismendez et al. (2023) further emphasized that the continued reliance on traditional or manual methods in demand forecasting in the poultry and other perishable food industries causes high variability in results due to a range of internal and external factors, leading to excess in inventory and major financial losses.  
2  
Beyond forecasting and supply chain issues, operational inefficiencies at the farm level also remain a significant concern. For medium- to large-scale poultry operations, manual egg collection remains one of the most time-consuming and labor-intensive tasks. In many cases, it accounts for 40–60% of daily labor hours, particularly in high-density housing systems such as H-type layer cages. This heavy reliance on manual labor not only increases operational costs but also limits overall efficiency, raising interest in potential automation and digital solutions that could significantly reduce workload while improving egg quality and flock welfare (Livi, 2025). In large-scale farms, egg collection and counting can take several hours to complete, resulting in eggs remaining in nesting areas for extended periods, which may affect product quality and farm productivity (Co., 2025). In addition, manual egg counting is highly prone to human error. Repetitive tasks and worker fatigue often lead to inaccurate recording of production data, including missed or inconsistent counts (FAO, 2013; NCBI, 2020).  
In order to address these issues, Putra et al. (2024) study showed that ARIMA (AutoRegressive Integrated Moving Average) model has shown an effective way to forecast regional chicken egg production in Indonesia, which contributes to national food planning and distribution. Their prediction showed an expected increase in total production from 12.5 billion eggs in 2025 to 18.76 billion in 2026, while also identifying regions with unstable data, which require better quality information and more adaptive models. Meanwhile, a by Silva et al. (2022) showed that the use of Industry 4.0 technologies, including the Internet of Things, Automation, Artificial Intelligence, and Blockchain in Southern Brazil resulted in higher productivity, reduced mortality rate in chickens, and lower operational costs. In addition this trend indicates that digitalized data and analytics not only help in better utilization of resources, but  
3  
also in supporting faster and more accurate decision-making in the global management of poultry farms. In line with this, various studies emphasized the need to adopt more advanced methods based on data, such as time series forecasting, machine learning, and collaborative planning systems to improve the accuracy of demand and producing forecasting, increase transparency in supply chain, and make resource allocation more efficient (Kulyk et al., 2025; Alfirdaus et al., 2025; Garcia-Arismendez et a., 2023).  
In the Philippines, the poultry industry is also one of the major agricultural sectors, serving as an important contributor to the country’s food supply and the income of many Filipinos. To meet the growing demand of the population and the market, egg production in the country continues to increase (PSA, 2025). However, manual egg counting processes are becoming increasingly insufficient to keep up with this growth, as traditional labor-intensive methods struggle to handle the rising production demands efficiently (Poultry Manual, 2020). Despite having access to data, many poultry operations lack the capacity to effectively analyze past trends and anticipate future performance. Their reliance on traditional processes in collecting data, such as paper-based, limits the ability to extract insights from the data, slow decision-making process, and reduces the ability to make use of available data for predicting future performance. According to Lementap et al. (2023), a time series study on broiler production in the Davao Region highlights key challenges in Philippine poultry operations. Many farms continue to rely on traditional, manual management and lack structured forecasting systems, which results in inefficient resource allocation, reactive decision making, production instability, and mismatches between supply and demand. Supporting this, Araújo et al. (2024) observed that many micro, small medium enterprises (MSMEs) often rely on their intuition to forecast sales that often lead to frequent errors and inefficiencies in operations due to insufficient use of relevant data in forecasting  
4  
decisions and structured feedback systems. To address these problems, Lementap et al. (2023) recommend the adoption of time-series forecasting models, such as ARIMA, along with the integration of data-driven monitoring systems and decision-support tools. These measures are intended to enable farmers to plan resources more effectively, enhance operational efficiency, and achieve more stable production outcomes. In addition, Araújo et al. (2024) propose complementing these strategies with data-driven forecasting and the establishment of more systematic marketing and feedback mechanisms to further support poultry operations. Meanwhile, the study of Jean et al. (2021), shows that proper and consistent data recording, including the use of time-series analysis and the Hen-Day Egg Production (HDEP) index is effective in forecasting egg production and in determining the appropriate time to cull hens in order to increase poultry farm profitability.  
At Central Luzon State University (CLSU), the Poultry Module I contributes to the university’s instructional activities and income-generating projects. Currently, the monitoring process in the poultry unit mainly relies on paper-based records for collecting and organizing data. Daily activities such as documenting egg production, tracking sales performance, and monitoring hen laying performance are recorded manually, including the manual counting of eggs. In addition, the computation of important productivity indicators such as percentage of Hen Day and Hen Housed is also performed manually. These calculations require time, effort, and careful checking to ensure the accuracy.  
Afterward, the recorded data are transferred occasionally to Microsoft Excel for basic reporting and storage. While this method still works to help for simple documentation, it remains at risk to human error, data inconsistency, delayed reporting, and limited analytical capability, such as automated analysis, trend analysis, and  
5  
forecasting. Furthermore, not having an integrated system limits the ability to forecast trends in egg production, sales, and laying performance of hens. As data volume increases, the traditional or manual monitoring process becomes less responsive to dynamic production conditions.  
This study proposes a system that uses predictive analytics techniques to predict and forecast trends such as egg production, sales and performance of hens, and making the process of recording data digitalize rather than the traditional process. Through an interactive dashboard that shows significant information, this study seeks to enhance the efficiency of the operations, improve decision-making, and strengthen the poultry management’s sustainability within the university. In addition, this study will also integrate an IoT-based automated egg counting system using computer vision, where a camera will be placed near the egg grading machine to automatically detect and count eggs, removing the need for manual counting, which will reduce the workload of the staff and help maximize their time for other important tasks.  
Client Profile  
This study will be conducted at Central Luzon State University (CLSU), located in Science City of Muñoz, Nueva Ecija, Philippines. Established in 1907, CLSU is recognized as a leading agricultural institution not only in Region III but throughout the country; it offers a diverse range of undergraduate, master's, and doctoral programs across various fields, and continues to serve thousands of students.  
The proposed system will be implemented at the CLSU Poultry Research Facility (Animal Production Office) located near the Animal Science Department and Small Ruminant Center, specifically in one selected poultry house. The poultry facility consists of four (4) houses, of which only three (3) are actively operating. Each poultry  
6  
house has approximately 1,800 to 2,000 layer hens, which are the main source of eggs for the facility.  
The poultry facility, called Poultry Module 1, is one of the university's income-generating projects (IGPs) and is managed by the University Business Affairs (UBAP). UBAP is one of the major programs of the university that is responsible for maintaining the inventory of various income-generating projects (IGPs), providing assistance in marketing products, and facilitating technologies developed from the various research and development centers of the university. Under UBAP there are divisions: Crop Production and Animal Production. The animal production division manages various livestock such as Layer, Broiler, and Swine Project.  
The egg collection is conducted three (3) times a day to maintain egg quality and prevent spoilage. The collection schedule is conducted every 10:00 AM for the first collection, 1:00 PM to 2:00 PM for the second collection, and 4:00 PM for the final collection. After the collection, the eggs are counted to determine the total egg production for each day. Aside from counting, eggs are also classified based on their size through an egg grading machine to determine their market classification. However, even with a mechanized egg grading process, the recording and monitoring of egg production data still remains manual.  
STATEMENT OF THE PROBLEM  
General Problem  
The poultry unit of Central Luzon State University faces a challenge in analyzing and forecasting the current production of eggs, sales performance, and laying performance of hens based on daily operational data. The traditional manual process of data collection and manual egg counting is time-consuming and leads to risk of human error, data inconsistency, and delayed reporting. Meanwhile, despite having enough  
7  
recorded data, the management finds it difficult to identify sudden changes in the production, decline in performance, and possible future trends. As a result, their capabilities to make faster and more effective decisions become limited. The absence of a system with predictive analytics and automated egg counting may cause slow processing of data, inability to forecast trends, and more difficult planning for future operations of the poultry unit.  
Specific Problem  
1\. The manual collection of data affects the accuracy of records and the efficiency of management in a poultry unit.  
2\. The time-consuming manual counting of eggs increases the workload of staff and limits their ability to efficiently manage time and other operational tasks.  
3\. The management struggles with planning and forecasting egg production, sales performance, and laying hen efficiency due to the lack of predictive analytics that utilizes historical data.  
4\. Limited analytical capability and data visualization affect the management’s ability to identify trends and irregularities in poultry operations.  
OBJECTIVES OF THE STUDY  
General Objective  
The main objective of this study is to develop and implement a predictive analytics system with digitalized data recording and automated egg counting that  
8  
maximizes the use of data, supports better decision-making, and increases operational efficiency.  
Specific Objectives  
Specifically, it aims:  
1\. Develop a digitalized system that can properly store egg production data, sales, and hen laying performance to improve management accuracy and efficiency.  
2\. Integrate an automated egg counting feature within the system to reduce the time-consuming process of manual counting and minimize the workload of staff.  
3\. Implement a predictive analytics module that uses historical data to forecast egg production trends and sales, supporting planning and decision-making.  
4\. Provide data visualization and report generation tools that present trends, irregularities, and performance metrics in poultry operations.  
SCOPE AND LIMITATION  
Scope  
This study will focus on the development and implementation of HENALYTICS: A Predictive Analytics System for Poultry Egg Production, Sales Forecasting, and Hen Laying Performance in CLSU. In accordance with the study’s objectives, the system aims to integrate a predictive analytics technique and digitalize the data collection process to facilitate data-driven decision-making in the CLSU Poultry Unit.  
●  
User Access Control: Only authorized people are allowed to access the system, including poultry staff and administrators.  
9  
●  
Data Digitalization and Management: Ensuring the accuracy of data and its consistency by having a centralized data recording and organization in a structured database.  
●  
Predictive Analytics for Egg Production: The system will predict the overall egg production of a single poultry house using historical data. The prediction will cover the total number of eggs produced over a given period, and will also include breakdowns based on egg sizes (such as small, medium, and large) to better reflect production distribution.  
●  
Sales Forecasting: The system will forecast the overall sales of a single poultry house using historical data. The prediction will include total sales performance as well as sales categorized by egg sizes. In addition, the model will also consider revenue generated from culled hens, since these are included as part of the unit’s sales.  
●  
Hen Laying Performance Monitoring: Monitoring the hen laying performance using particular production data to identify patterns and possible declines in hens’ productivity. The system will also use historical data to help predict when hens are approaching the culling stage based on decreasing production trends and performance indicators.  
●  
Automatic Egg Detection and Counting using YOLOv5: The system will implement the YOLOv5 (You Only Look Once) model for automatic egg detection and counting. Detection will be performed in real-time, where the model continuously processes the acquired data to identify and count eggs during the sorting process immediately.  
10  
Limitations  
●  
One Poultry House: In monitoring and managing data, the system limits only one poultry house within the CLSU Poultry Unit due to the dataset being restricted provided by the client. However, it does not cover other poultry houses or any external poultry farms.  
●  
Dependency on Historical Data: The predictive models’ accuracy and effectiveness depend on the quality and completeness of the available historical data.  
●  
System Accessibility: Only authorized users inside the CLSU Poultry Unit have the ability to access the system and it does not support public or external shareholders’ access.  
●  
Limited Variable Selection: The predictive analytics model to be implemented will only use historical data from the selected poultry house, including production and sales. It does not include other crucial variables such as disease outbreaks, weather, temperature conditions, and sudden disruptions in feed prices and markets.  
●  
Limitations on Detection Accuracy: The accuracy of the YOLOv5 model depends on the quality and quantity of the dataset used for training, so false detections may occur in some situations. In addition, the system is limited to detecting only normal eggs and does not cover the identification of broken or cracked eggs, so they may not be included in the count.  
11  
SIGNIFICANCE OF THE STUDY  
This study aims to benefit various stakeholders through improving data management, analysis, and performance monitoring in the poultry unit of Central Luzon State University. In accordance with the University’s commitment to the Sustainable Development Goals (SDGs), it specifically supports Decent Work and Economic Growth (SDG 8\) and Industry, Innovation, and Infrastructure (SDG 9). The system integrates sales forecasting using predictive analytics to help improve financial planning and increase revenue. Additionally, it strengthens agricultural activities and other income-generating projects, while promoting innovation and the use of digital tools for the modernization of poultry management. The system is designed to benefit the following:  
Poultry Management and Staff: Users will benefit from a digital and an efficient system for collection of data and analysis, which reduce errors and speed up decision-making.  
University Administration: Get reliable reports and forecasts to improve planning and resource allocation.  
Researchers and Students: Access reliable and organized data for future studies in poultry science and predictive analytics.  
Future IT and Agricultural Systems: Serve as a model for implementing digital and predictive solutions in livestock and farm management.  
12  
DEFINITIONS OF TERMS  
1\.  
ARIMA (Autoregressive Integrated Moving Average): a statistical model used to analyze historical egg production data and make short-term forecasts based on patterns and trends in past data.  
2\.  
Artificial Intelligence: the technology used in the system to analyze historical egg production and sales data in order to generate predictions and analytics.  
3\.  
Flock: A group of hens raised together in a poultry farm and managed as a single unit for egg production and monitoring purposes.  
4\.  
Fluctuations: refers to the variations or changes in egg production or sales over time that are analyzed by the system to identify patterns.  
5\.  
Hen Day: the percentage of eggs produced relative to the number of live hens on a given day and used as a measure of daily laying performance.  
6\.  
Hen Housed: the egg production rate calculated based on the total number of hens initially housed in the poultry facility.  
7\.  
Hen-Day Egg Production (HDEP): refers to the number of eggs produced per layer hen per day and used as a measure in the analysis of daily egg production.  
8\.  
Historical Data: refers to past records of egg production, sales, and related environmental factors, which serve as the basis for predictive modeling.  
9\.  
IoT (Internet of Things): A system of connected devices and sensors that collect, send, and process data over the internet to enable real-time monitoring and automation.  
10\.  
Irregularities: unusual or abnormal patterns observed in egg production or sales data during analysis.  
13  
11\.  
Layer Project: refers to the poultry production program focused on raising hens specifically for egg production.  
12\.  
Laying Performance: the productivity level of hens in producing eggs, evaluated using production data and performance indicators.  
13\.  
Machine Learning Models: the use of algorithms such as Linear Regression, Random Forest and LSTM to learn patterns from historical egg production and sales data to make predictions. It is also used for data-driven decision making in a poultry unit.  
14\.  
Past Trends: historical patterns in egg production and sales data used by the system as a basis for generating predictions.  
15\.  
Performance Metrics: the indicators used to evaluate poultry production efficiency, such as egg production rates and sales data.  
16\.  
Poultry: refers to domesticated chickens raised in the poultry facility for egg production.  
17\.  
Predictive Analytics: refers to the use of statistical and machine learning techniques to forecast egg production, sales, and hen performance, guiding the poultry unit’s decisions with data.  
18\.  
Regression Analysis: a technique used to identify the relationship between various factors such as egg production, sales, and laying performance, and use it to develop predictive models for forecasting.  
19\.  
Report Generation Tools: system features that automatically create reports from egg production and sales data for monitoring and analysis, such as PDF, Excel, or CSV formats.  
20\.  
Sales Performance: refers to the actual number of eggs sold over a period and how these figures are used to predict future sales trends.  
14  
21\.  
Time-series Analysis: refers to the use of historical data to identify trends and patterns over time.  
22\.  
Trends Analysis: refers to the analysis of the change and direction of egg production over a specified period.  
23\.  
YOLOv5 (You Only Look Once version 5): refers to the object detection model that will be used to automatically detect and locate eggs in images or video frames captured in the poultry area. It will help the system count eggs accurately in real time as part of the automated egg counting process.  
24\.  
Egg Counter: A system or process that automatically counts eggs, often using computer vision or sensors, to reduce manual counting and improve accuracy in poultry operations.  
15  
CHAPTER II  
REVIEW OF RELATED LITERATURE AND EXISTING ALTERNATIVES  
Introduction  
This chapter summarizes and critically analyzes the existing related literature and studies on the monitoring of egg production, hen laying performance, predictive analytics, forecasting, data-driven decision-making systems, and automated egg counting in poultry environments, which are relevant in conducting this study. Moreover, this chapter also discusses various approaches, specifically time-series models, machine learning techniques, fuzzy logic systems, and computer vision-based methods such as YOLO for egg detection and counting, along with their strengths and limitations. In conclusion, this chapter identifies research gaps through this study, and provides HENalytics a strong foundation to develop and guarantee that the proposed system will satisfy the needs of the CLSU Poultry Unit while developing innovation in predictive analytics and poultry data management.  
Previous Studies and Findings  
Egg Production Forecasting and Analytics Models. Several studies analyze various techniques for egg production forecasting and highlight the differences between traditional statistical models and modern machine learning methods in modeling laying rate, production trends, and variability of output in poultry farms.  
V. Gosselin (2024) claims that better predictions of egg production can be made with the help of data-driven forecasting techniques using historical production data. Different forecasting models were applied in the study, including Random Forest, Gradient Boosting, and Neural Networks, to identify patterns and trends in egg production over time. The results show that these models can improve prediction  
16  
accuracy, however, the effectiveness of the forecasting still depends on the quality and quantity of historical data used in the modeling. In comparison, Y. A. Adejola et al. (2025) focused on the performance of the Random Forest model in egg production forecasting. The analysis included both classification tasks, such as detecting abnormal production days, and regression tasks, such as predicting laying rate. The results show a higher level of predictive performance, supported by high AUC and low RMSE, indicating that Random Forest is effective in handling complex, non-linear, and multilinear production in poultry systems with fluctuating conditions.  
Similarly, N. Bumanis et al. (2023) showed that machine learning models such as LSTM, CNN, XGBoost, and Random Forest have higher forecasting accuracy in egg production compared to traditional non-linear models, even when using limited datasets. This suggests that while different models vary in architecture, most machine learning approaches are consistently effective in capturing patterns and variations in egg production across different production stages. On the other hand, T. G. Omomule et al. (2020) used a Mamdani Fuzzy Inference System to analyze egg production variables such as feed quality, body weight, and age of the hen. The results show that the method is effective in handling uncertainty and non-linearity in production data. However, compared to machine learning-based approaches, it is less scalable and offers limited automation in handling larger and more complex datasets.  
In local studies, Calanda (2025) shows that most poultry egg production businesses in the Philippines use trend analysis and descriptive statistics to identify daily and weekly production patterns. This method helps in simple forecasting and planning in poultry farm operations. Furthermore, Salvia and Valderama (2021) found that the use of time-series analysis and the Hen-Day Egg Production (HDEP) index is  
17  
effective in financial projection and break-even analysis, guiding decisions on culling period and optimizing income from egg production. For instance, forecasting with the use of the HDEP index shows 50% production rate serves as an economic break-even point for small poultry farms, which reflects its usefulness in basic decision-making but also highlights its limitation in handling dynamic production variability.  
Automated Egg Counting and Monitoring using Computer Vision. In addition to forecasting egg production, other studies focus on improving poultry farm operations through automation, particularly in egg counting and monitoring processes. Several studies analyze different implementation approaches for automated egg counting systems in poultry environments, particularly in how they design detection pipelines from image acquisition and pre-processing to object detection and count generation for farm monitoring.  
According to Jiang et al. (2024), the implementation used a modified YOLOv8-PG system for real-time egg detection, where key components of the original architecture were adjusted to improve feature extraction, small object detection, and handling of class imbalance. These modifications enhance detection stability and accuracy in complex environments while maintaining suitability for real-time deployment. In comparison, Wu et al. (2024) implemented an enhanced YOLOv8s-based machine vision system integrated with a ResNet-18 backbone and Shuffle Attention mechanism. The system utilizes fixed-position cameras and robotic patrol units to continuously capture poultry data, which are processed and converted into egg counts for monitoring. This shows that while YOLO-based systems differ in architecture and hardware integration, most implementations prioritize real-time detection accuracy and continuous monitoring capability.  
18  
On a broader level, Chai et al. (2023) highlighted that modern poultry systems increase the difficulty of manual egg collection and counting, which directly affects production tracking. In support of this, Neethirajan (2022) and Castro et al. (2023) showed that artificial intelligence and computer vision-based systems can automate egg detection and data collection, improving efficiency and accuracy in poultry farm monitoring. However, these systems often require complex setups, computational resources, and controlled environments, which may limit their practicality in smaller or resource-constrained farms.  
Overall, these studies suggest that while traditional statistical methods and machine learning models are both effective in egg production forecasting, machine learning approaches generally provide better predictive performance and adaptability, though their effectiveness still depends on data quality, model selection, and production complexity. In addition, computer vision approaches, particularly YOLO-based models, are effective in automating egg detection and counting, but existing implementations vary in complexity and deployment requirements, indicating a need for more practical and adaptable systems for real-world poultry operations.  
Existing Alternatives  
Egg Production Monitoring and Forecasting Approaches. Currently, various methods are used to monitor and predict egg production. These include the use of data-driven forecasting, which analyzes historical data to identify patterns and trends in production. This makes it easier to make predictions based on past data, however, this approach has limitations when data is lacking or insufficient. In such situations, the model’s ability to provide accurate predictions is weakened. Especially if there are  
19  
unexpected changes in production caused by factors such as environmental conditions, changes in feeding, and the condition of the hens.  
In some studies, analysis of egg production data is enhanced by using machine learning models such as Random Forest, LSTM, CNN, and XGBoost. By using these, more complex relationships between various factors affecting production can be analyzed, resulting in more accurate predictions. Its ability to learn from large datasets makes it more suitable for situations where production conditions experience frequent changes. In contrast, the model requires a higher level of technical knowledge, sufficient amount of data, and a more advanced process for model development. It is not always practical for farms with limited resources.  
There are also alternative methods that deal with uncertainty in production, such as fuzzy inference systems. This method is useful for analyzing factors, such as chicken age, feed quality, and weight, which may vary over time. It supports dealing with uncertain data and making decisions based on changing conditions. However, this is not as extensive as the capabilities of modern machine learning models when it comes to automatically processing large datasets, and generating more complex predictions.  
In local poultry operations, trend analysis, descriptive statistics, and Hen-Day Egg Production (HDEP) index are commonly used by poultry farms to track egg production. HDEP, along with trend and descriptive analysis, is often used to guide decisions in egg production management. It determines when the break-even point has been reached, which serves as a basis for the next step in the operation. While these are helpful in understanding the overall production pattern, their capabilities are limited when more detailed and complex data analysis is required. Even with the introduction  
20  
of more advanced technologies, many farms still use spreadsheets and manual trend analysis because of their low cost and ease of use. This method is helpful for simple financial tracking and planning, but it has limitations when it comes to deeper analysis and automated forecasting.  
Automated Egg Counting and Computer Vision Approaches. Various methods are used to automate egg counting in poultry environments. These approaches focus on detecting eggs in real time and converting visual information into accurate counts for effective monitoring and farm management.  
In some systems, a modified YOLOv8 is used where certain parts of the detection process are adjusted to better capture features, especially for small objects like eggs, and to deal with imbalance data. These changes help make real-time egg detection more reliable, so the system can produce more accurate egg counts even when the farm environment is complex. In other implementations, enhanced YOLOv8-based systems are paired with multiple cameras, such as fixed-position cameras and robotic patrol units, to continuously capture data inside the poultry environment. The captured frames are then processed using edge computing devices, and the detected eggs are converted into counts that are stored in cloud databases for monitoring. These setups can also run in different operation modes and support real-time streaming, making it possible to continue egg counting even when the internet connection is limited or unstable.  
On the other hand, most existing egg counting approaches rely on computer vision models like YOLOv5, YOLOv7, Faster R-CNN, and SSD. These models are mainly used to detect eggs from images or video frames and automatically convert those detections into counts, which helps reduce the need for manual counting in poultry farm  
21  
operations. However, even with these developments, there are still some limitations when it comes to practicality, system complexity, and actual deployment in real farm settings. Because of this, there is still a need for more efficient and adaptable solutions that are easier to implement, cost-effective, and more suitable for actual poultry farm conditions.  
Gaps in Existing Research  
Previous studies have shown that egg production prediction becomes more reliable and consistent when using data-driven approaches and various machine learning models. However, these models are limited by the availability of sufficient, complete, and well-structured historical data to perform these types of operations. On the other hand, conventional time-series and HDEP-based forecasting can be used for simple financial planning and trend forecasting, but they lack a high level of automation and flexibility.  
Models such as the Fuzzy Inference System can help manage uncertainty, but they are not scalable and lack automation for real-time decision making. Although advanced machine learning models such as Random Forest, LSTM, CNN, and XGBoost are more flexible and capable of predicting non-linear and dynamic production trends, they often require large datasets, high computational resources, and technical expertise, making their direct application impractical in small-scale poultry farms with limited resources.  
In terms of actual operations, manual egg counting and tracking in modern poultry systems is becoming increasingly difficult, which directly affects the accuracy of production tracking. In response, artificial intelligence and computer vision-based  
22  
systems are being used to automate egg detection and data collection. However, these systems often require complex setups, high computational resources, and controlled environments, which limits their practical use in small and medium-sized poultry farms.  
In addition, computer vision-based models such as YOLO have proven effective in real-time egg detection and counting. However, most existing implementations focus only on detection and monitoring and do not incorporate predictive analytics or production forecasting, in addition to their complexity in deployment.  
Therefore, a significant gap remains in developing a system that integrates predictive analytics, automated egg detection, and monitoring into a single integrated platform that is practical, scalable, and suitable for the local context. The present study aims to fill this gap by developing an adaptable and automated forecasting system for egg production, sales, and hen laying performance, and automatic egg counting using computer vision-based object detection. It is expected to help improve decision-making, production planning, and operational efficiency, which can lead to higher profits for poultry operations.  
Table 1: Gaps in Existing Research  
Research Title  
Key Findings  
Gaps/Limitation  
Current Project Solutions to these gaps  
Vincent Gosseli (2024) – Egg  
Production Forecasting  
Uses ML and simulation models (Random Forest, Gradient Boosting, and Neural Networks) to forecast eggs accurately.  
Requires large and complete historical data and complex setup. Not suitable for small farms with limited resources.  
The proposed system will only use the available records to generate forecasts. Designed to work effectively with data and making it practical for small-scale poultry  
23  
operations.  
Y.A. Adejola et al.  
(2025) \- Forecasting egg production performance and fluctuations in commercial freerange poultry systems using a random forest  
model  
Random Forest  
model has high predictive  
performance in forecasting egg production.  
Focused only on the model’s performance and not on the development of an integrated monitoring system.  
The system is not only a forecasting model but an integrated monitoring and analytic platform.  
N. Bumanis et al.  
(2023) \- Hen Egg Production Forecasting:  
Capabilities of Machine Learning  
Models in Scenarios with  
Limited Data Sets  
Machine Learning models such as  
LSTM, CNN,  
XGBoost, and Random Forest have shown to have higher forecasting accuracy than the traditional models.  
Focused only on comparing the accuracy of the models and not on the actual implementation of the system. The process is too complex and requires a high level of technical knowledge, sufficient data, and more advanced methods for model development.  
The system will be practical and adaptable, with sufficient predictive capability, but simpler and resource-efficient, making it suitable for local and smallscale poultry farms with limited data and resources.  
T.G. Omomule et al.  
(2020) \- Fuzzy prediction and pattern analysis of poultry egg production  
The use of the  
Mamdani Fuzzy  
Inference System to handle uncertainty in production  
Variables was effective.  
It is not as scalable and automated as modern machine learning frameworks.  
The proposed system provides data-driven  
analytics that are more scalable and easier to integrate into a monitoring platform.  
Calanda (2025) \- Development of a Web Application for  
Poultry Farm  
Monitoring and  
Control System  
Most poultry farms in the Philippines use trend analysis and descriptive statistics for production monitoring.  
Limited analysis and has no automated forecasting capability.  
The system provides an automated data recording,  
monitoring, and predictive analysis.  
Salvia and Valderama (2021) \- Layer Poultry  
Farming and Egg  
Production Profitability Model:Basis of  
Layer Harvesting  
Used the HDEP index and time- series analysis for financial projection and production evaluation.  
Focused only on performance evaluation and not on real-time monitoring or predictive systems.  
The proposed system will integrate monitoring, production tracking, and predictive analytics into one platform.  
24  
Jiang et al. (2024) \-  
Improved YOLOv8 Model for Lightweight Pigeon Egg Detection  
Used an enhanced YOLOv8 model with machine vision, real-time video streaming, and a robotic patrol system; achieved up to 98.9% egg detection accuracy in actual farm conditions.  
Requires complex hardware setup (robotic patrol, multiple systems) and high computational resources.  
The proposed system will design a simplified and cost-efficient YOLO-based detection system that is easy to deploy.  
Wu et al. (2025) \-  
Research on machine vision online monitoring system for egg production and quality in cage environment  
Proposed YOLO-based with high accuracy but lower computational load and fewer parameters; more suitable for mobile deployment.  
Focuses only on detection models and not integrated with monitoring or forecasting system.  
The system integrates the efficient detection model into a monitoring and forecasting system  
Chai et al. (2023) \-  
Tracking floor eggs with machine vision in cage-free hen houses  
Used machine vision for egg tracking in cage-free environments; demonstrated the capability of automation in real-world conditions.  
Focuses only on tracking/detection and no integration with analytics and decision-making.  
The proposed system will provide an integrated system with egg detection, monitoring, and predictive analytic Synthesis Based on the reviewed literature and studies, it can be observed that egg production forecasting and poultry monitoring systems have been widely developed using different approaches such as traditional statistical methods, time-series analysis, fuzzy logic systems, and machine learning models. In general, traditional methods like trend analysis, descriptive statistics, and Hen-Day Egg Production (HDEP) are commonly used in local poultry farms because they are simple and easy to apply for  
25  
basic monitoring and financial planning. However, these approaches are limited when it comes to handling complex and dynamic production conditions. On the other hand, studies show that machine learning models such as Random Forest, LSTM, CNN, and XGBoost provide higher accuracy and better ability to capture non-linear patterns in egg production, but they require large datasets, technical expertise, and higher computational resources, which may not always be practical for small-scale farms. Meanwhile, fuzzy logic systems are useful in dealing with uncertainty in production factors, but they lack scalability and automation compared to modern machine learning approaches. In addition, for automated egg counting and monitoring, computer vision-based systems such as YOLO variants and other deep learning models have been proven effective in detecting and counting eggs in real-time. These systems improve accuracy and reduce the need for manual counting, making poultry monitoring more efficient. However, most existing systems are still complex in terms of setup, require controlled environments, and are usually focused only on detection and counting without integration to predictive analytics or decision-support systems. Overall, existing studies show that while both predictive analytics and computer vision systems are already effective in their own functions, there is still a lack of a single system that combines forecasting, monitoring, and automated counting in one platform. This gap shows the need for a system that is more practical, easier to use, and suitable for real farm conditions, especially in local settings like CLSU Poultry Unit. In response to this, the present study aims to address these gaps by developing a system that combines data storage, egg production forecasting, and automated egg counting to help improve monitoring and decision-making in poultry operations.  
26  
CHAPTER III  
METHODOLOGY  
This chapter provides an overview of the systematic approach to designing, developing, and evaluating the predictive analytics system for poultry egg production, sales, and laying performance. The methodology will ensure clarity, consistency and alignment to meet the objectives that provide a structured framework for the development process and the continuous improvement of the system.  
Conceptual Framework  
In developing the proposed system, the researcher will follow the Agile Software Development approach. As illustrated in Figure 1, Agile is a flexible approach to project development that emphasizes collaboration, adaptability, continuous improvement, and the delivery of functional system increments throughout the development process. Unlike traditional linear development models such as Waterfall, where each team works separately before passing on to the next. Agile uses collaborative, cross-functional teams and emphasizes open communication, teamwork, adaptability, and trust (Atlassian, 2020).  
Guided by Agile principles, the system will be developed through incremental delivery of software components, where analysis, design, implementation, and testing occur in continuous and overlapping cycles. Agile emphasizes adaptability to changing requirements, as user needs and priorities may evolve throughout development. To manage this, Agile relies on continuous feedback from users and stakeholders to guide improvements in each software increment (GeeksforGeeks, 2019). This approach enables frequent delivery of functional outputs, allowing early evaluation and refinement of the system to ensure it remains aligned with poultry farm operations,  
27  
particularly in monitoring egg production and supporting decision-making for administrators.  
Figure 1: Agile Methodology (Jayathilaka, 2020\)  
Feasibility Study  
A feasibility study will be conducted for CLSU Poultry Module I, to determine whether the proposed system is practical and can be implemented. This analysis will focus on three main aspects: Technical Feasibility, Economic Feasibility, and Operational Feasibility.  
Technical Feasibility  
Technical Feasibility evaluates whether the chosen technologies and technological resources by the developers will be sufficient and available to develop and implement the proposed system. The proposed system will be developed using commonly used and reliable web development technologies, such as Python with the Django Framework for the backend For the user-interface, HTML, CSS, JavaScript, and Bootstrap will be used to create a responsive design, and SweetAlert for more  
28  
interactive alerts. The system will implement Regression (Multiple Linear) and Time-Series (ARIMA) using Python libraries to analyze historical data and generate predictive insights. In addition, a PostgreSQL database will be used to properly store and manage the system’s data, such as information and historical records used for analysis and prediction.  
For the automated egg counting feature, the system will use computer vision through YOLOv5, a well-known object detection model that is commonly used for real-time image processing tasks. It will be trained using poultry images to detect eggs captured from the system’s camera input. Once trained, the model will generate bounding boxes around detected eggs, which will then be processed by the system to produce accurate egg counts for monitoring and recording purposes.  
Table 3 presents the minimum system specifications, while Table 4 presents the recommended specifications for optimal system performance.  
Table 2: Minimum Specifications  
Component  
Specification  
Operating System (OS)  
Windows 10, Linux, or macOS  
Processor  
Intel Core i3 (8th Gen) / AMD Ryzen 3 (3rd Gen) or higher  
RAM  
8 GB  
Storage  
50 GB free disk space  
Web Server  
Nginx, PostgreSQL  
29  
Table 3: Recommended Specifications  
Component  
Specification  
Operating System (OS)  
Windows 10/11 (64-bit), Linux (Ubuntu/Mint), macOS (latest version)  
Processor  
Intel Core i5 (10th Gen) / AMD Ryzen 5 (5th Gen) or higher  
RAM  
8 GB or higher  
Storage  
100 GB or more free disk space (SSD recommended)  
Web Server  
Nginx, PostgresQL  
Economic Feasibility  
Economic feasibility will assess whether the benefits provided by the proposed system will be sufficient to explain and justify the costs required for its development and implementation. The proposed system will primarily use open-source software and development tools that will help reduce the overall cost of developing the system. Most of the technologies used such as programming frameworks, database management systems, and development environments are freely available and do not require expensive licenses. The only possible costs that may include minimal expenses such as the system hosting and domain.  
Compared to the current manual recording system used in the poultry facility, the proposed system will help recording of egg production and sales data advance, reduce human error in data entry, and facilitate the analysis of production trends. In addition, the ability of the system to provide forecasting of egg production, sales, and hen laying performance will help in better decision-making in the management of poultry production and can result in better operational planning and potential increase in the poultry unit's revenue. Therefore, the proposed system is considered economically feasible for the CLSU Poultry Module I.  
30  
Operational Feasibility  
Operational feasibility evaluates whether the proposed system can be effectively used by its intended users and whether it can improve existing operational processes. The system will be used by the Poultry Unit Manager (Admin) and two (2) assigned job-order staff. The Admin will be responsible for monitoring data, generating reports, and analyzing predictive outputs, while the staff will handle the daily input of egg production and sales data.  
The system is designed to be easy to use so both the Admin and staff can do their tasks without difficulty. Instead of relying only on manual recording, the system will use a centralized digital platform with an automated egg counting feature using YOLOv5. This means eggs can be detected and counted automatically during the grading process. Because of this, the need for manual counting is reduced, and the results are more accurate and faster. The staff will just check and confirm the outputs when needed.  
Since the roles of the users are clear and the system is not complicated to use, only minimal training will be needed. Overall, the system can help make the work faster, lessen errors, and support better decision-making. Therefore, the system is considered operationally feasible and suitable for use in the CLSU Poultry Module I.  
A. Requirements  
During the requirements gathering, the researchers communicated with poultry unit manager and staff to understand the existing process, needs, and data management process. Data were gathered through informal interviews, consultations, and feedback  
31  
collected to determine the functional and non-functional requirements of the system. This phase involves the creation of a requirements specification that describes the system’s scope, limitations, objectives, features, and user requirements.  
Questions for the interview:  
1\.  
Data Collection and Recording  
How do you currently collect and record the operations and performance of the poultry unit?  
What is the commonly used format or method for recording data (e.g. MS Excel, logbook)?  
What are the common problems or challenges you experience when manually recording data?  
How do reliance on manual processes affect operational accuracy and efficiency?  
What features or functionalities do you consider necessary for a system to enhance current operations.  
2\.  
Data Type and Management  
What types of data do you regularly collect in the poultry unit?  
Are there instances where errors or inconsistencies occur in the data collected? If so, how are they fixed?  
What are the difficulties in managing and storing collected data?  
32  
3\.  
Monitoring Chicken Production and Performance  
How do you currently measure chicken performance?  
What are the challenges in manually computing production metrics?  
How important is the regular monitoring of hen performance in your operations?  
What indicators or procedures do you rely on to detect changes in production performance?  
4\.  
Data Reporting and Accessibility  
How do you currently report or review collected data?  
What are the limitations of the current approach to providing clear information to management?  
How important is more organized and easily accessible reporting tools?  
Profile of Respondents and Selection Method  
The respondents of this study consist of selected personnel who are involved in the daily operations and management of the poultry production in the Central Luzon State University (CLSU) Poultry Research Facility, including poultry staff or employees responsible for collecting and organizing data such as egg production, sales, and hen laying performance, as well as the poultry unit manager, who manage production monitoring and decision-making related to poultry operations.  
33  
Aside from the end-users, the respondents also included IT professionals who will serve as system evaluators. They will evaluate the technical aspects of the proposed system based on quality criteria, to ensure functionality, reliability, and overall system performance.  
The selected respondents will be considered as the primary potential users of the proposed system as they are involved in recording, monitoring, analyzing egg production, sales data, and laying performance in the facility. They are expected to provide helpful information on the current process and the challenges of managing egg production data and sales based on their experience with the current manual recording system.  
Through purposive sampling, the respondents will be selected has relevant knowledge and experience in the operation of the poultry, ensuring that the participants in the study are sufficiently skilled to assist in the evaluation of the current system and in the development of the proposed system for more effective monitoring and forecasting of egg production, sales, and hen laying performance at the CLSU Poultry Module I.  
Data Gathering Procedure  
The data gathering procedure for this study will be conducted through several steps to ensure the proper analysis and development of the proposed system.  
First, the researchers will identify and select respondents from the CLSU Poultry Module I who had direct knowledge and experience in the daily operations of the poultry production. The selected participants were among staff and administrators involved in the monitoring of poultry operation.  
34  
Second, the researchers will conduct observations and interviews to understand the current process of egg collection and recording egg production and sales at the facility. In this process, important information will be gathered about the existing manual recording system, as well as the egg collection schedule and the method of monitoring egg production and laying performance of layer hens.  
Third, the researchers will also collect historical data from the poultry facility such as egg production data, sales, and laying performance data. These data will be used as a basis for analyzing production trends and developing a predictive analytics model that will be used in forecasting egg production, sales, and hen laying performance.  
Fourth, once the proposed system is developed, a demonstration of the system will be conducted with end-users to demonstrate its main functions of the system, including recording egg production data, recording egg sales, monitoring production performance, and viewing forecasting results and an evaluation will be conducted based on User Acceptance Testing (UAT). Following the demonstration, a structured evaluation process will be conducted using a questionnaire based on the ISO/IEC 25010 Software Quality Model. These questionnaires will be distributed to IT Professionals who will serve as evaluators of the system to measure its quality based on the criteria.  
Lastly, the responses that will be collected from the questionnaires will be organized, and prepared for statistical analysis to determine the overall effectiveness and quality of the system among its potential users. Furthermore, the researchers will administer an evaluation questionnaire to end-users and IT Professionals to obtain their feedback on the proposed system, which will be used for system refinement.  
35  
Ethical Concerns  
This study will adhere to every established standard for academic research. Before participating in the study, the participants will be asked to give informed consent and will be clearly informed about the purpose, scope, and voluntary nature of their involvement in order to ensure understanding and transparency. All data collected from end-users, IT Professionals, and poultry unit personnel will strictly remain confidential, including survey responses, interview insights, and evaluation feedback.  
No personal information will be used or disclosed for any purpose other than the study. The collected data will be used only for the purpose of research and improvement of the system. In addition, all research activities will strictly follow the ethical guidelines of the institution and will uphold principles of respect, responsibility, fairness, and integrity throughout the research process.  
B. Design  
This phase will be based on the results obtained from the Requirementphase. Through interviews, observations, and data collection conducted at CLSU Poultry Module I, the researchers will identify key challenges currently experienced in the poultry unit, such as the continued reliance on manual data recording and egg counting, inconsistencies in the data, difficulties in monitoring hen laying performance, and the absence of organized reporting and forecasting tools.  
These identified needs will serve as the basis for the design of the proposed system. In this phrase, the gathered requirements will be translated into structured representations of the system, including its System Architecture Design, Use-Case Diagram, Unified Modeling Language (UML), Data Flow Diagram (DFD), Entity  
36  
Relationship Diagram (ERD), and the Flow Chart. These elements will help ensure that the proposed system properly addresses the limitations of the current process and supports more efficient data management, monitoring, and predictive analytics.  
The System Architecture Diagram will show the overall structure of the egg management system and how its main components work together to support data processing and decision-making. It will include the user interface, egg grading machine, web server, machine learning module, and database. The system will handle automatic egg classification, data storage, and analysis to generate forecasts and insights, which will then be displayed to the Admin for monitoring and decision-making. (See Appendix A)  
The Use Case Diagram will show the system’s actors and main functions. It will include two users: Admin and Staff. The Admin will have full access to all features, while the Staff will be limited to managing records, sales, and flock information. It will also present the main system functions such as managing records, sales, and flock data, viewing analytics, and generating and exporting reports, along with how each user will interact with these processes. (See Appendix B)  
The Data Flow Diagram will show how data will move within the system and how the Admin and Staff will interact with it. The Admin will have full access to all processes, while the Staff will be limited to managing records, sales, and flock information. It will also illustrate the main system processes such as managing records, sales, and flock data, viewing analytics, and generating and exporting reports, along with how data will flow between these processes and the users. (See Appendix C)  
37  
The Unified Modeling Language (UML) Class Diagram of the proposed system will present its object-oriented structure through classes, attributes, and methods. The classes will be grouped into user authentication, flock management, production data, sales management, and machine learning. Core classes will include User, Flock, PoultryProductionRecord, EggSalesTransaction, and ModelVersion. Each class will contain methods that will define actions for managing and storing data within the system. (See Appendix D)  
The Entity Relationship Diagram (ERD) of the system will present the database structure and relationships between its entities. It will include nine tables, with Flock as the central entity linked to production, grading, sales, and forecast records. User management will use auth\_user and UserProfile with a one-to-one relationship. Sales and machine learning data will be stored in related tables such as SalesItem, ModelVersion, HarvestForecast, and SalesForecast, with constraints applied to ensure data integrity and prevent duplicates. (See Appendix E)  
Lastly, the Flow Chart Diagram System FlowChart will present the System Flowchart of the proposed HENalytics system, depicting the complete step-by-step flow of operations from system start to end using standard flowchart symbols. The process begins when a user visits the login page, after which the system validates the credentials and redirects the user to either the Admin or Staff dashboard depending on their assigned role. Staff users can record daily poultry production data, egg sales, and trigger the YOLOv5 egg grading process, all of which are saved to the PostgreSQL database. Once sufficient data of at least 30 days has been accumulated, the ML pipeline is executed — performing feature engineering, an 80/20 chronological train-test split, and training both the Multiple Linear Regression models for harvest prediction and the  
38  
ARIMA models for sales forecasting per egg grade. The resulting 30-day forecasts are saved to the database and displayed on the Admin dashboard, after which the user may log out to end the session. (See Appendix F)  
Data Processing and Predictive Modelling  
This section will aim to describe how data will be processed and used to develop predictive models for egg production, sales, and hen performance, as well as for automated egg counting in the poultry unit. The dataset for this study will come from a poultry house with approximately 1,800-2,000 chickens and use at least a year’s worth of data. The data consists of daily records of egg production, sales, and performance of chickens.  
Before starting to build a predictive modeling, the data will go through a series of preprocessing steps to ensure its quality and reliability. Preprocessing is considered a critical step in data science and machine learning, which aims to clean and transform raw data to be suitable for training the model (Ault et al., 2019). Data cleaning involves identifying and correcting missing or incorrect entries, including missing values, and inconsistent entries to minimize errors and enhance the quality of the data. This step will be critical in preprocessing and will directly affect the performance of the predictive model (Signh et al., 2020). Following this, data digitization will be performed, where handwritten data is converted into digital format. This process enables the data to be further processed, cleaned, and transformed for machine learning applications (Alexander et al., 2022).  
39  
To examine the factors affecting egg production and sales, Multiple Linear Regression will be used. At the same time, ARIMA will be applied to explore production patterns and provide forecasts for trends within a year. The dataset will be split into training and testing sets in a 4:1 ratio, with 80% allocated for training and 20% for testing. The training set will be used to teach the model patterns and relationship in the data. The testing test will be used to test its performance on data that the model has not yet seen. This ensures that the model is learning real patterns and not just memorizing training data (GeeksforGeeks, 2023).  
In addition to structured data modeling, the study will also include an image-based data processing pipeline for automated egg counting using the YOLOv5 object detection model. Before training the model, raw data in the form of images or extracted video frames of eggs will be collected to serve as the training dataset. The data needs to reflect actual operating conditions, such as variation in lighting, camera angles, and overlapping eggs, to make sure the model performs reliably in real scenarios (Li. et al., 2025).  
Since the grading machine physically separates eggs into different size-based columns, the system will utilize predefined regions of interest (ROIs) aligned with these columns. Detected eggs from YOLOv5 will be mapped to their corresponding regions to support per-column counting. Each egg in the images will be labeled using bounding boxes along with corresponding class labels. To further improve the model’s performance, image preprocessing techniques such as resizing, normalization, and data augmentation (e.g., rotation, flipping, and brightness adjustments) will be applied (Ultralytics, 2023).  
40  
C. Development  
In this development phase, the focus will be on implementing the proposedsystem based on the approved requirements and system design produced in the earlier phases. Here, the researchers will turn the design into a working web-based application that will support egg production monitoring, sales recording, hen laying performance tracking, and predictive analytics. The development process will follow an iterative and incremental approach, where system components will be developed, tested, and refined continuously within each cycle to ensure functionality, reliability, and alignment with the intended requirements.  
Development tools and technologies:  
The overall structure of the system will be discussed in this part, where it uses various systems materials, tools, and emerging technologies to ensure successful development of the proposed system. These technologies will be selected in accordance with their efficiency, effectiveness, compatibility, accuracy, and appropriate use in developing a reliable web-based predictive analytics system.  
In developing the proposed system, the researchers will choose Python as their primary programming language because of its capabilities in data processing and strong support for machine learning. Python is known as a high-level interpreted programming language that is simple and easy to learn, yet capable of performing complex computational tasks. It is commonly used to create a variety of applications, especially in machine learning, scientific computing, and data science (Raschka, 2021). Django will be used as well as a framework to properly manage backend logic, data handling,  
41  
and communication between the user and the system. To create a responsive and user-friendly interface, HTML, CSS, and Javascript will be used along with Bootstrap. Historical data will be stored in PostgreSQL for use in analysis and prediction, and will serve as the basis of the system's data management. During the entire development process, researchers will use Visual Studio Code for coding and Github for version control and better collaboration.  
The system will also use Machine Learning, a branch of Artificial Intelligence, to learn patterns and relationships from historical data. Machine learning focuses on building systems that learn from data and continuously improve performance over time (Craig, 2024). Furthermore, its algorithms will be trained to recognize patterns and make predictions without directly programming each process (NNLM, 2021). Rather than relying solely on manual analysis, the system will apply various machine learning techniques to improve decision-making process in egg production, sales, and hen laying performance. Specifically, the system will use Multiple Linear Regression (MLR) to determine the relationship between various factors that affect production and performance (Taylor, 2021). At the same time, it will also utilize ARIMA for time series analysis, which will examine trends and patterns of data over time to produce more reliable forecasts (Saadeddin, 2025). In addition to this, the study will incorporate computer vision techniques using the YOLOv5 object detection model to support automated egg detection and counting, improving the accuracy and organization of data collection within the system.  
42  
D. Testing  
Once the implementation is completed, the proposed system will be tested to ensure that it works properly and provides accurate results. Manual testing will be conducted where each functionality of the system is manually checked by the researchers, to identify errors and ensure its proper operation, as well as user testing by the potential users, such as staff and administrators to be able to determine whether it is user-friendly and meets all the identified needs of the CLSU Poultry Module I.  
Following this, the system will be tested based on ISO 25010 standards to measure its quality in terms of functional suitability, performance efficiency, interaction capability, security, and reliability. During this process, the identified deficiencies or errors will be corrected, and if it is necessary, the researchers will return to the implementation phase to make the necessary changes and improvements to the system.  
After ensuring the proper functioning of the system, User Acceptance Testing (UAT) will be conducted to evaluate the system based on the user experience of the potential users. This will measure the usability, performance, functional correctness and completeness, data integrity, timeliness, and confidentiality and availability of the system. The process will determine the user’s acceptance of the system and their level of satisfaction with using it.  
E. Deployment  
The deployment phase will involve the implementation of the developed web-based system in the intended operational environment of the CLSU Poultry Module I. In this phase, the system will be made accessible to users, particularly the poultry unit manager (Admin) and staff, through a web browser.  
43  
The deployment process will include the installation and configuration of the system on the server, as well as the setup of the PostgreSQL database for storing and managing data such as egg production records, egg classification, sales transactions, and flock information. All system components will be verified to ensure proper functionality in the actual environment. The deployment will also include the integration of an automated egg counting component, where data captured during the egg grading process will be transmitted to the system for recording and processing, reducing reliance on manual counting.  
Prior to full use, final checks will be conducted to ensure that all modules, including data recording, inventory management, analytics, and egg counting, are functioning as intended. Basic user orientation will also be provided to guide users in operating the system. This phase will ensure that the system is fully operational, accessible, and ready to support poultry production monitoring and decision-making.  
F. Review  
This phase will involve gathering feedback from end-users, including poultry staff and administrators, and IT professionals who will use the proposed system to evaluate its performance, usability, and effectiveness in recording, monitoring, and forecasting egg production, sales, and hen laying performance. Regular demonstrations and reviews of the system will be conducted, where key features such as data recording, production monitoring, and predictive analytics results will be demonstrated to obtain comments and suggestions from end-users and IT Professionals for further improvement of the system. Retrospective reviews will also be conducted to assess the development process and identify areas that need to be changed or improved in the next development phase.  
44  
The ISO/IEC 25010 Software Quality Model will be used as the basis for the evaluation of the system by IT Professionals, which will focus on characteristics such as functional suitability, performance efficiency, reliability, interaction capability, and security. On the other hand, User Acceptance Testing (UAT) will be conducted with end-users, including poultry staff and administrators, to measure the usability, performance, functional correctness and completeness, data integrity, timeliness, and confidentiality and availability of the system.  
Among the nine characteristics of ISO/IEC 25010, some aspects, such as compatibility and flexibility, will not be included in the evaluation because the proposed system does not require integration with other systems and is designed only for a single operating environment. Meanwhile, safety will also not be included because the system is not considered a critical-risk system that has a direct impact on human safety. On the other hand, in User Acceptance Testing (UAT) standards, the testing will focus only on the usability, performance, and functional accuracy of the system. Other aspects, such as scalability and other advanced system features are not included because they are not covered by the prototype and are not the main focus of the study.  
All the feedback gathered and the results of the evaluation will be used to identify the necessary changes and improvements to the system, which will serve as the basis for the refinement and final deployment of the proposed system. According to ISO 25010, the quality factor encompasses nine quality attributes, and the User Acceptance Testing encompasses eight quality attributes, which are as follows:  
Table 4: Quality Characteristics of ISO/IEC 25010  
Types and Definition  
45  
Functional Suitability  
•  
Functional completeness \- Degree to which the set of functions covers all the specified tasks and intended users' objectives.  
•  
Functional correctness \- Degree to which a product or system provides accurate results when used by intended users.  
•  
Functional appropriateness \- Degree to which the functions facilitate the accomplishment of specified tasks and objectives.  
Performance Efficiency  
•  
Time behaviour \- Degree to which the response time and throughput rates of a product or system, when performing its functions, meet requirements.  
•  
Resource utilization \- Degree to which the amounts and types of resources used by a product or system, when performing its functions, meet requirements.  
•  
Capacity \- Degree to which the maximum limits of a product or system parameter meet requirements.  
Interaction Capability  
•  
Appropriateness recognizability \- Degree to which users can recognize whether a product or system is appropriate for their needs.  
•  
Learnability \- Degree to which the functions of a product or system can be learnt to be used by specified users within a specified amount of time.  
•  
Operability \- Degree to which a product or system has attributes that make it easy to operate and control.  
•  
User error protection. Degree to which a system prevents users against operation errors.  
•  
User engagement \- Degree to which a user interface presents functions and information in an inviting and motivating manner encouraging continued interaction.  
•  
Inclusivity \- Degree to which a product or system can be used by people of various backgrounds (such as people of various ages, abilities, cultures, ethnicities, languages, genders, economic situations, etc.).  
•  
User assistance \- Degree to which a product can be used by people with the widest range of characteristics and capabilities to achieve specified goals in a specified context of use.  
•  
Self-descriptiveness \- Degree to wich a product presents appropriate information, where needed by the user, to make its capabilities and use immediately obvious to the user without excessive interactions with a product or other resources (such as user documentation, help desks or other users).  
•  
Faultlessness \- Degree to which a system, product or component performs specified functions without fault under normal operation.  
46  
Reliability  
•  
Availability \- Degree to which a system, product or component is operational and accessible when required for use.  
•  
Fault tolerance \- Degree to which a system, product or component operates as intended despite the presence of hardware or software faults.  
•  
Recoverability \- Degree to which, in the event of an interruption or a failure, a product or system can recover the data directly affected and re-establish the desired state of the system  
Note. Adapted from Systems and software engineering \- Systems and software Quality Requirements and Evaluation (SQuaRE) \- System and software quality models (ISO/IEC 25010:2011).  
Table 2 presents the product quality evaluation based on the ISO/IEC 25010 standard. It comprises six quality characteristics that are used to assess both the internal and external quality of the system, as evaluated by IT experts.  
Table 5: User Acceptance Testing (UAT)  
Characteristics  
Definition  
Usability  
It will focus on evaluating whether the system is user-friendly, intuitive, and meets the expectations of end-users to ensure that it is easy to navigate and can be used to perform tasks efficiently.  
Performance  
It will focus on assessing whether the system can handle multiple users, maintain its stability, and perform tasks within an acceptable time frame  
Functional Correctness and Completeness  
It will focus on verifying that all software features work according to the specified business requirements and that no critical functionality has been omitted during the development phase.  
Timeliness  
It will focus on ensuring that the system can process transactions quickly and provide immediate responses that are in line with the speed required for business operations.  
Confidentiality and Availability  
It will focus on confirming that sensitive data remains secure and that the system is available to users at any time required.  
Data Integrity  
It will focus on verifying that the system maintains the accuracy, consistency, and reliability of data.  
Note. Adapted from User Acceptance Testing (UAT) Guidelines and Software Testing Standards, and modified based on the UniSpace System evaluation requirements. (\[ISTQB\], 2018).  
47  
Table 3 presents the results of the User Acceptance Testing (UAT), which includes selected evaluation criteria used to assess the system’s usability, performance, and overall acceptability based on the feedback of end-users.  
Table 6: Likert Evaluation Scale  
SCALE  
NUMERIC VALUE  
DESCRIPTION OF RATING  
5  
4.50-5.00  
Highly Acceptable  
4  
3.50-4.49  
Acceptable  
3  
2.50-3.49  
Moderately Acceptable  
2  
1.50-2.49  
Slightly Acceptable  
1  
1.00-1.49  
Not Acceptable  
Note. Adapted from Likert Evaluation Scale. (Rensis Likert 1932\)  
As presented in Table 4, the evaluation tool for determining the quality of the proposed system, based on the ISO/IEC 25010 standard, will be administered to IT professionals. In addition, User Acceptance Testing (UAT) will be carried out among end-users, particularly the poultry staff and administrators. The evaluation will utilize a Likert scale with corresponding numerical values and descriptive interpretations to assess the system’s effectiveness. These ratings will indicate how well the system fulfills user requirements and achieves its intended objectives. Once the proposed system meets the identified sub-characteristics of product quality, both IT professionals and end-users will evaluate its effectiveness using the given scale. This method ensures a systematic assessment of the proposed system, confirming its compliance with the ISO/IEC 25010 quality standards and its acceptability through User Acceptance Testing (UAT).  
Scale Interpretation  
5 – Strongly Agree  
4 – Agree  
48  
3 – Neutral  
2 – Disagree  
1 – Strongly Disagree  
49  
REFERENCES  
Alexander, J. Trent, et al. “Digitizing Hand-Written Data with Automated Methods: A Pilot Project Using the 1990 U.S. Census.” Journal of Economic and Social Measurement, vol. 46, no. 2, May 2022, pp. 95–108, https://doi.org/10.3233/jem-220484. Accessed 13 Apr. 2026\.  
Araújo, G. M. C., de Silva, A. L., da Gonçalves, H. S., & Correia, A. M. M. (2024). Management of micro and small enterprises (MPEs): Sales forecasting in the retail sector. Revista de Gestão Social e Ambiental, 18(9), e08295. https://doi.org/10.24857/rgsa.v18n9-170  
Ault, S. V., Liao, N., & Musolino, L. (2019). 2.4 Data Cleaning and Preprocessing \- Principles of Data Science | OpenStax. Openstax.org; OpenStax. https://openstax.org/books/principles-data-science/pages/2-4-data-cleaning-and-preprocessing?  
Bumanis, N., Kviesis, A., Paura, L., Arhipova, I., & Adjutovs, M. (2023). Hen Egg Production Forecasting: Capabilities of Machine Learning Models in Scenarios with Limited Data Sets. Applied Sciences, 13(13), 7607\. https://doi.org/10.3390/app13137607  
Calanda, F. P. (2025). Development of a Web Application for Poultry Farm Monitoring and Control System. Lecture Notes in Networks and Systems, 1–12. https://doi.org/10.1007/978-981-96-6935-6\_1  
Castro, F. L. S., Chai, L., Arango, J., Owens, C. M., Smith, P. A., Reichelt, S., DuBois, C., & Menconi, A. (2022). Poultry industry paradigms: connecting the dots. Journal of Applied Poultry Research, 32(1), 100310\. https://doi.org/10.1016/j.japr.2022.100310  
50  
Co., P. (2025, October 25). Manual Egg Collection vs. Egg Conveyor Belt In Poultry Layer Farm: A Cost AnalysisP. Guangzhou Zhongshen Ribbon Product Co., Ltd. https://www.poultrymanurebelt.com/news/manual-egg-collection-vs-egg-conveyor-belt-in-poultry-layer-farm-a-cost-analysisp-251592.html?  
Craig, L., & Tucci, L. (2024). What is machine learning? Guide, definition and examples. Search Enterprise AI; TechTarget. https://www.techtarget.com/searchenterpriseai/definition/machine-learning-ML?  
Cser, T. (2024, September 23). Acceptance Testing: A Step-By-Step Guide. Www.functionize.com. https://www.functionize.com/automated-testing/acceptance-testing-a-step-by-step-guide  
Donato, H. (2023, January 3). What Are The Phases Of Scrum? Www.workamajig.com. https://www.workamajig.com/blog/scrum-methodology-guide/scrum-phases  
Eggs for Philippines: Running Efficient Poultry Egg Production Operation \- Poultry Manual. (2020, May 21). Poultry Manual. https://poultrymanual.com/2016/05/21/eggs-for-philippines-running-efficient-poultry-egg-production-operation  
Garcia-Arismendiz, J., Huertas-Zúñiga, S., Lizárraga-Portugal, C. A., Quiroz-Flores, J. C., & Garcia-Lopez, Y. J. (2023). Improving Demand Forecasting by Implementing Machine Learning in Poultry Production Company. International Journal of Engineering Trends and Technology, 71(2), 39–45. https://doi.org/10.14445/22315381/ijett-v71i2p205  
51  
GeeksforGeeks. (2019, June 18). Agile Software Process and its Principles. GeeksforGeeks.https://www.geeksforgeeks.org/software-engineering/agile-software-process-and-its-principles/  
GeeksforGeeks. (2022, November 24). User Acceptance Testing (UAT) Software Testing. GeeksforGeeks. https://www.geeksforgeeks.org/software-testing/user-acceptance-testing-uat/  
GeeksforGeeks. (2023, November 29). Training data vs Testing data. GeeksforGeeks. https://www.geeksforgeeks.org/python/training-data-vs-testing-data/  
Glamac. (2025, February 24). Revolutionizing Poultry Farming: The Role of Artificial Intelligence in Enhancing Productivity. Glamac \- Courage to Reach Horizon. https://www.glamac.com/blog/revolutionizing-poultry-farming-the-role-of-artificial-intelligence-in-enhancing-productivity/  
Inflectra. (n.d.). Complete Guide To Scrum Methodology | Inflectra. Www.inflectra.com. https://www.inflectra.com/Solutions/Methodologies/Scrum.aspx  
ISO/IEC 25010\. (n.d.). Iso25000.com. https://iso25000.com/index.php/en/iso-25000-standards/iso-25010  
Jamille, J. (2024, December 9). Current Challenges in the Philippine Poultry Market: A Crisis of Prices, Supply, and Sustainability – Industry Strategic Science and Technology Plans (ISPs) Platform. Dost.gov.ph. https://ispweb.pcaarrd.dost.gov.ph/current-challenges-in-the-philippine-poultry-market-a-crisis-of-prices-supply-and-sustainability  
Janagaran (jana@poultry.care. (2025, September 3). Egg Losses in Poultry Farming – Control with Smart Software Solutions. PoultryCare.  
52  
https://www.poultry.care/blog/egg-losses-in-poultry-farming-control-with-smart-software-solutions?  
Jayathilaka, C. (2020, July 30). Agile Methodology. Medium. https://medium.com/@chathmini96/agile-methodology-30ec4cdf3fc  
Jean, K., Salvia, G., & Valderama, J. (2021). Layer Poultry Farming and Egg Production Profitability Model:Basis of Layer Harvesting. International Journal of Arts, 2\. https://www.mail.ijase.org/index.php/ijase/article/download/46/55/199?  
Jeffhraim Balilla, Bondoc, M., Castro, K. A., & Padua, A. (2023, May 20). A 6-YEAR FORECAST OF EGG, RICE, AND ONION RETAIL PRICES IN THE PHILIPPINES: AN APPLICATION OF ARIMA AND... ResearchGate; unknown. https://www.researchgate.net/publication/370910461\_A\_6-YEAR\_FORECAST\_OF\_EGG\_RICE\_AND\_ONION\_RETAIL\_PRICES\_IN\_THE\_PHILIPPINES\_AN\_APPLICATION\_OF\_ARIMA\_AND\_SARIMA\_MODELS  
Jiang, T., Zhou, J., Xie, B., Liu, L., Ji, C., Liu, Y., Liu, B., & Zhang, B. (2024). Improved YOLOv8 Model for Lightweight Pigeon Egg Detection. Animals, 14(8), 1226–1226. https://doi.org/10.3390/ani14081226  
Khaswa Giovani Simanungkalit, Muhammad Fikri Azhari, Muhammad ihsan Raditya, Putra, I. L., & Asido, V. (2025). Analysis of Egg Production Forecasting by Province in Indonesia Using the ARIMA Algorithm. JOMLAI: Journal of Machine Learning and Artificial Intelligence, 4(1), 31–37. https://doi.org/10.55123/jomlai.v4i1.5765  
53  
Lementap, J. W., & Masinading, G. M. (2023). ARIMA MODELLING ON THE BROILER CHICKEN PRODUCTION OF DAVAO REGION. Advances and Applications in Statistics, 88(2), 245–263. https://doi.org/10.17654/0972361723048  
Li, J., Ma, W., Wei, Y., & Wang, T. (2025). Enhanced YOLOv8 for Robust Pig Detection and Counting in Complex Agricultural Environments. Animals, 15(14), 2149\. https://doi.org/10.3390/ani15142149  
LIVI Poultry Farm Equipment. (2025). Automated Egg Collection System Saves 70% Labor | Smart Poultry Farming Guide. Livipoultrycage.com. https://www.livipoultrycage.com/news/automated-egg-collection-system-labor-reduction.html?  
Machine Learning. (2021). NNLM; National Library of Medicine. https://www.nnlm.gov/resources/data-glossary/machine-learning?  
Mitchell, F. (2025). Automation in Poultry Industry. Farrelly Mitchel (Food & Agribusiness Specialists). https://farrellymitchell.com/automation-in-poultry-industry/  
Naeem, M., Jia, Z., Wang, J., Poudel, S., Manjankattil, S., Adhikari, Y., Bailey, M., & Bourassa, D. (2025). Advancements in machine learning applications in poultry farming: a literature review. Journal of Applied Poultry Research, 100602\. https://doi.org/10.1016/j.japr.2025.100602  
Nassar, F. S. (2025). Poultry production under threat: Framework to counter misinformation and protect food security. Poultry Science, 104(12), 106050\. https://doi.org/10.1016/j.psj.2025.106050  
54  
Nassar, F. S. (2026). Strategic role of poultry production sciences in shaping the future of global food security and strengthen sustainability. Poultry Science, 105(5), 106617\. https://doi.org/10.1016/j.psj.2026.106617  
Neethirajan. (2022). Google Scholar. Google.com. https://scholar.google.com/scholar\_lookup?title=Automated%20tracking%20systems%20for%20the%20assessment%20of%20farmed%20poultry\&publication\_year=2022\&author=S.%20Neethirajan  
Omomule, T. G., Ajayi, O. O., & Orogun, A. O. (2020). Fuzzy prediction and pattern analysis of poultry egg production. Computers and Electronics in Agriculture, 171, 105301\. https://doi.org/10.1016/j.compag.2020.105301  
Online Browsing Platform (OBP). (2019). Iso.org. https://www.iso.org/obp/ui/\#iso:std:iso-iec:25010:ed-1:v1:en  
Petr Lolek, & Veit Electronics. (2024, March 20). 5 Core Challenges in Manual Poultry Weighing. Poultryscales.com. https://poultryscales.com/academy/5-core-challenges-in-manual-poultry-weighing  
Pihak (2026). Principles-of-Data-Science-WEB-1. Scribd. https://www.scribd.com/document/857799869/Principles-of-Data-Science-WEB-1  
Raschka, S., Patterson, J., & Nolet, C. (2021). Machine Learning in Python: Main Developments and Technology Trends in Data Science, Machine Learning, and Artificial Intelligence. Information, 11(4), 1–44. MDPI. https://doi.org/10.3390/info11040193  
Rehkopf, M. (2025). Scrum Sprints. Atlassian. https://www.atlassian.com/agile/scrum/sprints  
55  
Richey, R. C. (2021). Developmental Research: The Definition and Scope. Ed.gov. https://eric.ed.gov/?id=ED373753  
Sachin Subedi, Ramesh Bahadur Bist, Yang, X., & Chai, L. (2023). Tracking floor eggs with machine vision in cage-free hen houses. Poultry Science, 102(6), 102637–102637. https://doi.org/10.1016/j.psj.2023.102637  
Scrum.org. (2020). What Is Scrum? Scrum.org. https://www.scrum.org/resources/what-scrum-module  
Singh, N., & Gaur, B. (2020). Data Preprocessing: A Step-by-Step Guide for Clean and Usable Data. Türk Bilgisayar ve Matematik Eğitimi Dergisi, 10(2), 1148–1153. https://doi.org/10.61841/turcomat.v10i2.14384  
Tan, I. (2025, May 9). Philippine poultry production rises 9.3% in Q1 2025\. AviNews. https://avinews.com/en/philippine-poultry-production-rises-9-3-in-q1-2025/  
Taylor, S. (2021, April 21). Multiple Linear Regression. Corporate Finance Institute. https://corporatefinanceinstitute.com/resources/data-science/multiple-linear-regression/  
Yusuf Adewale Adejola, Sibanda, T. Z., Ruhnke, I., Johan Boshoff, Saluna Pokhrel, & Welch, M. (2025). Forecasting Egg Production Performance and Fluctuations in Commercial Free-Range Poultry Systems using a Random Forest Model. Smart Agricultural Technology, 101380–101380. https://doi.org/10.1016/j.atech.2025.101380  
Zaina Saadeddin. (2024, September 9). ARIMA for Time Series Forecasting: A Complete Guide. Datacamp.com; DataCamp. https://www.datacamp.com/tutorial/arima  
56  
Ultralytics. (2023). YOLOv8. Docs.ultralytics.com. https://docs.ultralytics.com/models/yolov8/\#overview  
What Is Likert Scale \- Definition & How to Use It | QuestionPro. (n.d.). QuestionPro. https://www.questionpro.com/blog/what-is-likert-scale/  
Wu, Z., Zhang, H., & Fang, C. (2024). Research on machine vision online monitoring system for egg production and quality in cage environment. Poultry Science https://doi.org/10.1016/j.psj.2024.104552  
57  
APPENDICES  
Appendix A  
System Architecture  
Figure 2: System Architecture  
58  
Appendix B  
Use Case Diagram  
Figure 3: Use case Diagram  
59  
Appendix C  
Data Flow Diagram  
Figure 4: Data Processing and Predictive Modelling  
Figure 5: Image Processing and Object Detection  
60  
Appendix D  
Unified Modeling Language  
Figure 6: Unified Modeling Language  
61  
Appendix E  
Entity Relationship Diagram  
Figure 6: Entity Relationship Diagram  
62  
Appendix F  
Flowchart Diagram  
Figure 7: Flowchart Diagram  
63  
Appendix G  
Data Dictionary  
Table 7: auth\_user  
Table 8: UserProfile Table Name Column Name Data Type Constraint Description  
UserProfile  
id  
INT  
PK, Auto Increment  
Unique identifier for each user profile  
user\_id  
INT  
FK → auth\_user  
References the associated auth\_user record  
role  
VARCHAR(10)  
Not Null  
User role in the system: staff or admin  
full\_name  
VARCHAR(150)  
Not Null  
Display name of the user  
assigned\_house  
INT  
Nullable  
House number the staff member is assigned to manage  
created\_at  
DATETIME  
Auto Timestamp  
Date and time the profile record was created  
Table 9: Flock Table Name Column Name Data Type Constraint Description  
id  
INT  
PK, Auto Increment  
Unique identifier for each flock batch  
house\_no  
INT  
Not Null  
House number where the flock is housed (1, 2, or 3\) Table Name Column Name Data Type Constraint Description  
auth\_user  
id  
INT  
PK, Auto Increment  
Unique identifier for each system user  
username  
VARCHAR(150)  
Not Null, Unique  
Login username used for authentication  
password  
VARCHAR(128)  
Not Null  
Hashed password managed by Django  
email  
VARCHAR(254)  
Nullable  
Email address of the user  
is\_active  
BOOLEAN  
Not Null, default True  
Indicates whether the user account is active  
date\_joined  
DATETIME  
Not Null  
Timestamp when the user account was created  
64  
Flock  
breed\_strain  
VARCHAR(100)  
Not Null  
Breed or strain name of the laying hens (e.g. Lohmann Brown)  
date\_started  
DATE  
Not Null  
Date when the flock batch was placed in the house  
initial\_hen\_count  
INT  
Not Null  
Number of hens at the start of the flock cycle  
status  
VARCHAR(10)  
Not Null  
Current status of the flock: active or retired  
notes  
TEXT  
Nullable  
Optional remarks about the flock batch  
Table 10: PoultryProduction Record Table Name Column Name Data Type Constraint Description  
PoultryProduction Record  
id  
INT  
PK, Auto Increment  
Unique identifier for each production record  
flock\_id  
INT  
FK → Flock, Not Null  
References the flock batch this record belongs to  
production\_date  
DATE  
Not Null, Unique w/ flock  
Date of the production record; unique per flock  
age\_weeks  
INT  
Not Null  
Age of the flock in weeks on the record date  
age\_days  
INT  
Not Null, Auto-computed  
Age of the flock in days; computed from flock start date on save  
live\_hen\_count  
INT  
Not Null  
Number of live hens in the house on the record date  
daily\_mortality  
INT  
Not Null, default 0  
Number of hens that died on the record date  
daily\_culls  
INT  
Not Null, default 0  
Number of hens culled on the record date  
feed\_consumed\_bags  
DECIMAL(5,2)  
Not Null  
Total feed consumed in bags on the record date  
eggs\_collected  
INT  
Not Null  
Total number of eggs collected on the record date  
hen\_day\_production  
DECIMAL(5,2)  
Not Null  
Hen-day production percentage: eggs ÷ live hens × 100  
65  
hen\_housed\_production  
DECIMAL(5,2)  
Not Null  
Hen-housed production percentage: eggs ÷ initial hens × 100  
feed\_conversion\_ratio  
DECIMAL(4,2)  
Not Null  
Feed conversion ratio: feed consumed per kg of eggs produced  
management\_remarks  
TEXT  
Nullable  
Optional remarks such as vitamins administered or veterinary visits  
entered\_by\_id  
INT  
FK → auth\_user, Nullable  
References the staff user who submitted this record  
created\_at  
DATETIME  
Auto Timestamp  
Date and time the record was saved into the system  
Table 11: EggGradingRecord Table Name Column Name Data Type Constraint Description  
EggGradingRecord  
id  
INT  
PK, Auto Increment  
Unique identifier for each grading record  
flock\_id  
INT  
FK → Flock, Not Null  
References the flock batch this grading record belongs to  
grading\_date  
DATE  
Not Null, Unique w/ flock  
Date of the grading session; unique per flock  
grade\_jumbo  
INT  
Not Null, default 0  
Count of Jumbo grade eggs collected  
grade\_extra\_large  
INT  
Not Null, default 0  
Count of Extra-Large (XL) grade eggs collected  
grade\_large  
INT  
Not Null, default 0  
Count of Large grade eggs collected  
grade\_medium  
INT  
Not Null, default 0  
Count of Medium grade eggs collected  
grade\_small  
INT  
Not Null, default 0  
Count of Small grade eggs collected  
grade\_pullets  
INT  
Not Null, default 0  
Count of Pullet grade eggs (small eggs from young hens)  
grade\_peewee  
INT  
Not Null, default 0  
Count of Peewee eggs; sub-standard, not sold  
cracked\_eggs  
INT  
Not Null, default 0  
Count of cracked or broken eggs; recorded as waste  
source  
VARCHAR(10)  
Not Null, default hardware  
Data source: hardware (auto) or manual (fallback entry)  
66  
created\_at  
DATETIME  
Auto Timestamp  
Date and time the grading record was created  
Table 12: EggSales Transaction Table Name Column Name Data Type Constraint Description  
EggSales Transaction  
id  
INT  
PK, Auto Increment  
Unique identifier for each sales transaction  
flock\_id  
INT  
FK → Flock, Not Null  
References the flock batch whose eggs were sold  
sale\_date  
DATE  
Not Null  
Date when the egg sale transaction occurred  
recorded\_by\_id  
INT  
FK → auth\_user, Nullable  
References the staff or admin user who recorded the sale  
notes  
TEXT  
Nullable  
Optional remarks about the transaction such as buyer details  
created\_at  
DATETIME  
Auto Timestamp  
Date and time the transaction record was created  
Table 13: SalesItem Table Name Column Name Data Type Constraint Description  
SalesItem  
id  
INT  
PK, Auto Increment  
Unique identifier for each sales line item  
transaction\_id  
INT  
FK → EggSalesTransaction, Not Null  
References the parent sales transaction this item belongs to  
grade  
VARCHAR(20)  
Not Null  
Egg grade sold: jumbo, xl, large, medium, small, or pullets  
quantity\_trays  
DECIMAL(8,2)  
Not Null  
Number of trays sold for this grade (1 tray \= 30 eggs)  
price\_per\_tray  
DECIMAL(8,2)  
Not Null  
Selling price per tray in Philippine Peso  
total\_amount  
DECIMAL(10,2)  
Not Null, Auto-computed  
Total revenue for this line: quantity\_trays × price\_per\_tray  
Table 14: ModelVersion Table Name Column Name Data Type Constraint Description  
id  
INT  
PK, Auto Increment  
Unique identifier for each model training version  
67  
ModelVersion  
model\_type  
VARCHAR(20)  
Not Null  
Type of model trained: harvest (MLR) or sales (ARIMA)  
trained\_at  
DATETIME  
Auto Timestamp  
Date and time when the model training was completed  
triggered\_by  
VARCHAR(10)  
Not Null  
Who triggered retraining: auto (cron) or admin (manual)  
r2\_score  
DECIMAL(5,4)  
Nullable  
R² coefficient of determination for regression harvest model  
mae  
DECIMAL(8,4)  
Nullable  
Mean Absolute Error of the model on the held-out test set  
rmse  
DECIMAL(8,4)  
Nullable  
Root Mean Square Error of the model on the test set  
aic\_score  
DECIMAL(10,4)  
Nullable  
Akaike Information Criterion score used for ARIMA model selection  
arima\_order  
VARCHAR(20)  
Nullable  
Selected ARIMA order (p,d,q) chosen by auto\_arima via lowest AIC  
pkl\_path  
VARCHAR(255)  
Nullable  
File path to the saved .pkl model file on the server disk  
is\_active  
BOOLEAN  
Not Null, default False  
Indicates whether this model version is currently in use for predictions  
training\_rows  
INT  
Nullable  
Number of data rows used to train this model version  
Table 15: HarvestForecast Table Name Column Name Data Type Constraint Description  
HarvestForecast  
id  
INT  
PK, Auto Increment  
Unique identifier for each harvest forecast row  
flock\_id  
INT  
FK → Flock, Not Null  
References the flock batch this forecast belongs to  
model\_version\_id  
INT  
FK → ModelVersion, Not Null  
References the model version that generated this forecast  
forecast\_date  
DATE  
Not Null  
Future date for which the egg count is predicted  
grade  
VARCHAR(20)  
Not Null  
Egg grade for this prediction: jumbo, xl, large, medium, small, or pullets  
predicted\_qty  
INT  
Not Null  
Predicted number of eggs for the specified grade and date  
created\_at  
DATETIME  
Auto Timestamp  
Date and time the prediction row was written to the database  
68  
Table 16: SalesForecast Table Name Column Name Data Type Constraint Description  
SalesForecast  
id  
INT  
PK, Auto Increment  
Unique identifier for each sales forecast row  
model\_version\_id  
INT  
FK → ModelVersion, Not Null  
References the ARIMA model version that generated this forecast  
forecast\_date  
DATE  
Not Null  
Future date for which the sales volume is predicted  
grade  
VARCHAR(20)  
Not Null  
Egg grade for this prediction: jumbo, xl, large, medium, small, or pullets  
predicted\_trays  
DECIMAL(8,2)  
Not Null  
Predicted number of trays to be sold for the specified grade and date  
created\_at  
DATETIME  
Auto Timestamp  
Date and time the prediction row was written to the database  
