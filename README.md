# About FIXX

FInding eXploits by eXample if a novel approach focused on detecting cross-site scripting (XSS) vulnerabilities in PHP application. Using a CVE containing information about a known XSS in an application, FIXX extracts useful information to find similar locations throughout the same application that are susceptible to XSS and also finds paths to such locations.

FIXX has been built using Python and Cypher Queries. We present the details of using FIXX to find similar vulnerabilities below - 

## Table of Contents
1. About The Project
    - Built With
2. Getting Started
    - Prerequisites
    - Running FIXX
    - Interpreting Results
3. Contact

# Getting Started
Before running FIXX on any application, it is important to obtain a known vulnerability or exposure (CVE) from [mitre.org](https://cve.mitre.org/index.html) that contains the corresponding application for which you wish to find other vulnerabilities.

## Pre-requisites
- Most common terminal command <br>
    ```
  python main.py -n *application_name* *argument_type*
    ```
- Docker Engine setup
  * The primary step in running our approach is to have Docker setup and running
  * The details of setting up docker have been provided in the docs folder
- Application setup
  * Download the source code of the application corresponding to the CVE being processed. Make sure the version matches the one mentionedin the CVE description.
  * Pull the source code written to help build the code property graph (CPG) of the application as well as run the similarity approach
  * Build the Code Property Graph of the application using the terminal command given above and replace *application_name* with the name saved the application and *argument_type with *<code> --buildcpg </code> option (This step can take a couple minutes to a few hours depending on the size of the application)
  * Load the CPG of the application using the same terminal command and application name along with the *argument_type* as <code> --loadcpg </code>
 
## Running FIXX
- Now we are ready to run FIXX on the application
- Using the <code> --similarity </code> option begin the process of computing the number of exploitable paths present in application

## Interpreting Results
