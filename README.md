# About FIXX

This artifact contains details about Finding Exploits by Example (FIXX)

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
  python navev.py -n *application name* *argument_type*
    ```
- Docker Engine setup
  * The primary step in running our approach is to have Docker setup and running
  * If you are on Windows, you can download Docker Desktop and create a docker image
  * If you are on Mac
  * Make sure the ports from your local machine are mapped to the corresponding ports inside the docker container
- Application setup
  * Download the source code of the application corresponding to the CVE being processed
  * Pull the source code written to help build the code property graph (CPG) of the application as well as run the similarity approach
  * Build the Code Property Graph of the application using the <code> --buildcpg </code> option (This step can take a couple minutes to a few hours depending on the size of the application)
  * Load the CPG of the application using the <code> --loadcpg </code>
 
## Running FIXX
- Now we are ready to run FIXX on the application
- Using the <code> --similarity </code> option begin the process of computing the number of exploitable paths present in application

## Interpreting Results
