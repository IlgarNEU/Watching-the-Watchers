# Artifact Appendix

Paper title: **Watching the Watchers: Privacy Analysis of U.S. Smart TV Automatic Content Recognition**

Requested Badge(s):
   [+] **Available**
   [+] **Functional**
   [+] **Reproduced**


## Description 

Paper Title: Watching the Watchers: Privacy Analysis of U.S. Smart TV Automatic Content Recognition
Authors: Ilgar Mammadov; Het Rutul Joshi; Daniel J. Dubois; David Choffnes;

@inproceedings{watchingthewatchers27,
  title={Watching the Watchers: Privacy Analysis of U.S. Smart TV Automatic Content Recognition},
  author={Ilgar Mammadov and Het Rutul Joshi and Daniel J. Dubois and David Choffnes},
  booktitle={Proceedings on Privacy Enhancing Technologies Symposium (PoPETs)},
  year={2027}
}

This research artifact includes:
- Scripts to control smart TVs (Section 4.2)
- Scripts to reproduce the results from the dataset we provide (Section 4), or from other researchers' network datasets collected from smart TVs 
- Datasets (small dataset inside the "data" folder, larger dataset on Zenodo and/or Google Drive)
- Blocklist for ACR endpoints (Appendix B.2)
- Per-TV record of candidate endpoints remaining after each filtering step (the CSVs underlying Table 4)
- Detailed reproduction instructions





## Repository Structure

```
.

├── README.md                  # This file
├── LICENSE                    # License file
├── scripts/
│   ├── data_processing        # scripts to preprocess network data
│   ├── filter_endpoints       # filtering steps (Section 5.1)
│   ├── acr_behavior_analysis  # ACR behavior analysis (Section 6)
│   ├── requirements.txt       # Python dependencies (pinned versions)
│   ├── tv_control             # scripts to control smart TVs (Section 4)       
├── data/
│   ├── analysis_figures       # final plots of ACR endpoint behavior will be generated here
│   ├── csvs                   # .csv files from .pcap files will be generated here
│   ├── domain_list_csvs       # the list of domains contacted during each experiment will be generated here
│   ├── experiment_timings     # log of experiment timings are here
│   ├── filtering_results      # results of each filtering step will be generated here
│   ├── individual_domain_csvs # .csv files containing the network activity to each endpoint will be generated here
│   ├── ip_to_dns_mappings     # mappings of IP addresses to DNS/SNI names will be generated here
│   ├── parquets               # .parquet files generated from source .pcap files or downloaded from the data storage will be here
│   ├── pcaps                  # .pcap files will be downloaded here
│   ├── periodicity_results    # results of periodicity filter will be here
│   ├── reference              # helper list of domains for cross-OS filtering are here
│   ├── volume_logs            # individual logs of traffic ratio/volume for each endpoint will be generated here
├── Endpoints remaining after each filtering step/
│   ├── os_name                # the list of endpoints remaining after each filtering step (Section 5.1) for each OS
├── Blocklist/
│   ├── blocklist.txt          # tested and verified blocklist for ACR endpoints


```

---



### Security/Privacy Issues and Ethical Concerns

Our experiments on our own devices did not entail human subjects or ethical concerns. 
We do not provide the data collected from VIDAA OS which uses plaintext communication
to transfer sensitive household data, including PII. 


## Basic Requirements

### Hardware Requirements

For the full dataset:
1. High CPU compute power (would take >6h on a laptop)
2. High Storage (>10GB)

For reproducibility tests:
1. The dataset for all smart TVs require ~1TB storage. However, for reproducibility purpose, we provide smaller dataset which requires <10GB storage and can be run on a laptop. The scripts were run successfully on Ubuntu and MacOS.

### Software Requirements

1. The experiments were run successfully on Ubuntu 26.04 and MacOS.
2. The scripts do not require a special version of the listed operating systems, as long as Python 3 and TShark are available. They were tested using Python 3.13.7.
4. Python virtual environment is required.
5. requirements.txt contains the list of required dependencies.
7. The dataset required to run the artifacts include .pcap files containing network traces of smart TVs, their compressed .parquet version, timing logs of experiments in .csv files, and network trace dataset to specific ACR endpoints as .csv files. Depending on the steps to be completed, only a subset of the dataset is required. We provide timing logs as .csv files inside /data/experiment_timings folder. In the corresponding steps, we provide the instructions to obtain the remaining necessary dataset.

### Estimated Time and Storage Consumption

The overall time required to run the analysis scripts end-to-end for one smart TV requires up to 24 hours with intensive human involvement. However, we provide mid-level results which can be used to reduce the number of steps for reproducing the results. Depending on the number of steps and scale, the required time can be decreased to 1 hour.

The storage requirement also depends on the number of steps to be completed. The overall dataset requires ~1TB storage. The overall dataset for only one smart TV requires ~100 GB storage. However, we provide mid-level dataset, which decreases this requirement to ~1 GB.

## Environment 

### Accessibility

The TV-control scripts, data processing and analysis code, ACR endpoint blocklist, and per-TV record of candidate endpoints after each filtering step are provided in the following GitHub repository. The repository also contains the small dataset, such as timing logs of the experiments, which is necessary to run the scripts. We provide the larger dataset necessary to run the scripts in Zenodo. However, Zenodo has a storage limitation. Our full dataset is ~1 TB. To overcome this limitation and support reproducibility, we follow this methodology:

1) The dataset from all smart TVs (which is ~1TB) is provided using Google Drive as .pcap files: https://drive.google.com/drive/folders/1QLnMNb8Zke8iQVpddlIYvZm2yjCTTrLX?usp=sharing
2) We also provide a subset of source .pcap data on Zenodo to support usage of the preprocessing scripts: 
3) To support straightforward reproducibility, the necessary header fields are extracted and compressed into a .parquet file per smart TV. Each .parquet file is ~ 1GB. These files are stored on Zenodo and also Google Drive: (https://drive.google.com/drive/u/0/folders/1kZ7DJ1FXc1jHn60JEaWy5QPzz81Y8cci)
Using those .parquet files, one can skip the data preprocessing step and still complete the filtering and ACR behavior analysis steps.
4) .csv files containing the network activity to each ACR endpoint on Zenodo. One can use this dataset to skip filtering steps and complete the ACR behavior analysis step.


https://github.com/IlgarNEU/Watching-the-Watchers.git

### Set Up the Environment

1. Clone the repository

```bash
git clone https://github.com/IlgarNEU/Watching-the-Watchers.git
```

2. Install Python 3.7 or higher (3.13 is recommended)

You can download the latest version of Python from the official website: https://www.python.org/downloads/

3. Install tshark
On Linux:

```bash
sudo apt-get update
sudo apt-get install -y tshark
sudo usermod -a -G wireshark $USER
newgrp wireshark
```

On macOS:
Check if Homebrew is installed:

```bash
brew --version
```

If not installed, install it:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then install tshark:

```bash
brew install wireshark
```

3. Go inside "scripts" folder on terminal, create a virtual environment using pyenv, and activate it:

cd Watching-the-Watchers/scripts
python3 -m venv venv
source ./venv/bin/activate

4. Install dependencies:
pip install -r requirements.txt


### Testing the Environment 

Test dependency installation:

python -c "
import pandas, numpy, scipy, matplotlib, gdown
print('✓ All Python packages installed')
"

Expected to see: ✓ All Python packages installed

Test tshark installation: 

tshark --version

Expected to see a specific version of tshark installed, for example: TShark (Wireshark) 4.6.8 (Git commit e677bf052328).

## Artifact Evaluation

### Main Results and Claims

#### Main Result 1: Section 6.1 - Observed ACR-Attributable Traffic (RQ1)

To answer the research question 1, i.e. to understand which scenarios are subject to ACR tracking, we examine the time series graphs generated inside /data/analysis_figures/<os_name> folders. When we see high, periodic traffic during an experiment (the plot names mention the experiment/scenario name), we interpret that ACR tracking is active during that scenario. When we see low-amplitude or rare traffic in comparison to other scenarios, we interpret that ACR tracking is deactive during that scenario. We have summarized the ACR-subject scenarios and non-ACR scenarios in the takeaways subsection of Section 6.1 as well as Figure 6 (a) heatmap.

#### Main Result 2: ACR opt-out effectiveness (RQ2)

When ACR is opted-out by a user, we expect to see low or no network traffic to the ACR endpoints. However, our results show that for Tizen OS and SmartCast OS, the ACR activity continues during opted-out state. To interpret the results from the plots generated inside analysis_figures folder, one should examine the plots named with (ACR=OFF). 

### Experiments
1) Processing/Analysis scripts. These scripts consist of three stages:

   data_processing: The network traces in .pcap format are renamed, converted to .csv files containing the necessary data fields, and merged into one .parquet file per smart TV.

   filter_endpoints: The ACR endpoints are defined through numerous filtering steps. (Section 5.1)

   acr_behavior_analysis: The scripts to create individual .csv files for certain domains after some filtering steps, and the analysis scripts for exploring ACR behavior using the identified ACR endpoints. (Section 6)

We provide how to complete all the mentioned steps to reproduce the results. However, one can choose to complete only the last step to produce the plots, which is the shortest step.


#### Download Datasets

We provide datasets for reproducibility. The list of dataset categories is described below:

1) Network traces as .pcap files.
2) Necessary fields extracted and merged into one .parquet file per smart TV.
3) One .csv file per ACR endpoint with necessary fields.

The number/size of .pcap files is large, and the time required to download them can be long (the exact time depends on your internet connection).
The dataset to be downloaded depends on which stages will be run.
We recommend continuing to read these instructions and downloading the dataset only when needed, as we also provide certain mid-level results to support skipping the implementation of certain steps if not necessary. Once you have decided which dataset to download, the following commands can be used to download them.



Please use one of the following for <os_name>: 
tizen, webos, roku_roku, roku_tcl, google, fire, smartcast, xumo, google_sony_non_acr, google_hisense, google_tcl


1) Network traces as .pcap files:
   python download_dataset.py pcaps <os_name>

   For example, python download_dataset.py pcaps tizen

2) Necessary fields extracted and merged into one .parquet file per smart TV:
   python download_dataset.py parquets <os_name>

3) One .csv file per ACR endpoint with necessary fields:
   python download_dataset.py csvs <os_name>



#### Step 1: Data Processing

NOTE! We expect that the provided commands are run inside scripts folder.

The first step of the pipeline is data processing, where the .pcap files for each smart TV are renamed, converted to .csv, and merged into a large .parquet file. 
The scripts to complete this processing step are provided inside "scripts/data_processing/" folder.

- Time/Storage requirements: The required time/storage to complete this step depends on the preference of the user. If one prefers to run the scripts on the full dataset, it may take considerable time also depending on the internet connection.

##### Network Traces
The network traces (.pcap files) for all smart TVs are provided in this Google Drive link (https://drive.google.com/drive/folders/1QLnMNb8Zke8iQVpddlIYvZm2yjCTTrLX?usp=sharing). They can be downloaded to the data/pcaps/<os_name> folders as described in Step 1. We recommend downloading only a subset of the files for the purpose of evaluating data processing scripts, as the number/size of the total network traces is considerably large.


##### Rename Pcaps
Our IoT data collection system enumerates and names .pcap files with sequence numbers. For example, xxx.pcap, xxx.pcap1, xxx.pcap2, etc.
First, we need to rename the files to have correct .pcap extension.

Please use one of the following for <os_name>: tizen, webos, roku_roku, roku_tcl, google, fire, smartcast, xumo, google_sony_non_acr, google_hisense, google_tcl

      python ./data_processing/renamePcapsFromIotSystem.py <os_name> 

- Expected output: Inside data/pcaps/<os_name> folder, the .pcap files are correctly renamed.

##### Convert .pcap files to .csv files
We extract the useful fields from the .pcap files and store them in .csv format.

Please use one of the following for <os_name>: tizen, webos, roku_roku, roku_tcl, google, fire, smartcast, xumo, google_sony_non_acr, google_hisense, google_tcl

      python ./data_processing/runSniPcapToCsv.py <os_name>

- Expected output: Inside data/csvs/<os_name> folder, the .csv files are created corresponding to individual .pcap files.

##### Merge all .csv files into one large parquet for each smart TV
We merge .csv files into one .parquet file per smart TV

Please use one of the following for <os_name>: tizen, webos, roku_roku, roku_tcl, google, fire, smartcast, xumo, google_sony_non_acr, google_hisense, google_tcl

      python ./data_processing/mergeCsvs.py <os_name>

- Expected output: Inside data/parquets/<os_name> folder, the merged_all.parquet files are generated.





#### Step 2: Filter Endpoints (Section 5)

NOTE! We expect that the provided commands are run inside scripts folder.

- Time: 1 human-hour + 2 compute-hour per TV
- Storage: ~1.5 GB per TV

Part of the methodology is to define the ACR endpoints for each smart TV through numerous filtering steps. This folder (and partly acr_behavior_analysis folder) provides the scripts for the filtering steps. Since the smart TVs contact a large number of endpoints and generate a large amount of network traffic, certain filtering steps take a considerable time (~1 hour). To skip this stage for our dataset, we also provide the .csv files for the traffic to/from the identified ACR endpoints, so that the analysis scripts can be run for those endpoints. Please see how to download the files using the script in Step 1, or you can find them in Google Drive link (https://drive.google.com/drive/folders/14AnQWI5DxC-03ya1vj1wfGKy54shhc4f?usp=sharing)

##### Create initial list of endpoints contacted by the smart TV
The domain_analysis_by_ip_and_sni.py script creates an ip_to_domain_mapping.csv file which maps IP addresses to domain names.
Also, this script creates the list of endpoints contacted by the smart TV during each experiment session.

Please use one of the following commands for <os_name>: tizen, webos, roku_roku, roku_tcl, google, fire, smartcast, xumo, google_sony_non_acr, google_hisense, google_tcl

      python ./filter_endpoints/domain_analysis_by_ip_and_sni.py <os_name>

      python ./filter_endpoints/mixed_domain_analysis_by_ip_and_sni.py <os_name>

The expected output is ip_to_dns_mapping.csv file inside data/ip_to_dns_mapping/<os_name> folder and the list of domains for each experiment inside data/domain_list_csvs/<os_name> folder.

##### Filter well-known services
Once we have the list of all endpoints, we remove the ones for well known services. 

Please use one of the following for <os_name>: tizen, webos, roku_roku, roku_tcl, google, fire, smartcast, xumo, google_sony_non_acr, google_hisense, google_tcl

      python ./filter_endpoints/filter_domains.py <os_name>

The expected output is well-known-services-filtered.csv inside /data/filtering_results folder.   

##### Group by base name
We group the fully qualified domain names into base domain names. 

Please use one of the following for <os_name>: tizen, webos, roku_roku, roku_tcl, google, fire, smartcast, xumo, google_sony_non_acr, google_hisense, google_tcl

      python ./filter_endpoints/group_base_domains.py <os_name>

The expected output is grouped_by_base.csv inside /data/filtering_results folder.   

##### Opt-in filter
We detect the endpoints contacted during a number of experiments above the defined threshold:

Please use one of the following for <os_name>: tizen, webos, roku_roku, roku_tcl, google, fire, smartcast, xumo, google_sony_non_acr, google_hisense, google_tcl

      python ./filter_endpoints/quantify_domain_existence.py <os_name>

The expected output is frequent_domains_top.csv inside /data/filtering_results folder.  

##### cross-OS filter
NOTE! This step can be run in one of the two alternative methods:
1) The scripts until that point can be run for all TVs, so that in this step, the enpoints common to at least two smart TVs can be detected and eliminated. For that method:

      python ./filter_endpoints/crossOS_filtering.py

2) If there is a time limitation to running the scripts for all TVs first, we provide the list of domains common to at least two smart TVs, so that the script can be run for each smart TV, even if the previous steps have not been completed for all TVs:

      python ./filter_endpoints/crossOS_filtering_from_list.py

The expected output is frequent_domains_top_filtered.csv inside /data/filtering_results folder.  

##### traffic ratio

To detect the traffic ratio for the individual domains, so that we can identify the endpoints with higher outgoing traffic, we need to create the .csv files for each individual endpoint remaining from the previous steps. 

Please use one of the following for <os_name>: tizen, webos, roku_roku, roku_tcl, fire, smartcast, xumo, google_sony_non_acr, google_hisense, google_tcl

      python acrfileCreation.py <os_name>

      python ./filter_endpoints/create_the_final_domain_list.py <os_name>

      python manager_volume_analysis.py <os_name>


Because Sony Google TV uses DNS over HTTPS, a separate script is used to create the ACR endpoint traffic database and its analysis:

      python sony_acrfileCreation.py google

The expected output is individual .csv files names as domain names inside /data/individual_domain_csvs/ folder and ratio.csv file inside /data/filtering_results folder.

##### periodicity analysis
Then we define the list of domains with periodic behavior:

NOTE! Please note that certain TVs do not need to be tested for periodicity since only one domain is left in the previous step. (Table 4)



Please use one of the following for <os_name>: tizen, webos, roku_roku, roku_tcl, smartcast, google_tcl


      python ./filter_endpoints/periodicity_analysis.py <os_name>

Expected output: The list of endpoints with periodic behavior will be printed on the terminal and saved to data/periodicity_results/<os_name>/periodic_domains.csv file

### Step 3: ACR behavior analysis (Section 6)
- Time: 30 human-minutes + 30 compute-minutes
- Storage: < 1 GB

If the previous steps were not completed, we also provide the .csv files for the traffic to/from the identified ACR endpoints, so that the analysis scripts can be run for those endpoints. Please see how to download the files using the script in Step 1, or you can find them in Google Drive link (https://drive.google.com/drive/folders/14AnQWI5DxC-03ya1vj1wfGKy54shhc4f?usp=sharing)

To generate the time series and CDF figures for network traffic to ACR endpoints, the following commands are used. The analysis is completed on those figures to define the ACR activity and answer each research question.

How to interpret the results: To answer the research question 1, i.e. to understand which scenarios are subject to ACR tracking, we examine the time series graphs generated inside /data/analysis_figures/<os_name> folders. When we see high, periodic traffic during an experiment (the plot names mention the experiment/scenario name), we interpret that ACR tracking is active during that scenario. When we see low-amplitude or rare traffic in comparison to other scenarios, we interpret that ACR tracking is deactive during that scenario. We have summarized the ACR-subject scenarios and not ACR-subject scenarios in the takeaways subsection of Section 6.1 as well as Figure 6 (a) heatmap.

When ACR is opted-out by a user, we expect to see low or no network traffic to the ACR endpoints. However, our results show that for Tizen OS and SmartCast OS, the ACR activity continues during opted-out state. To interpret the results from the plots generated inside analysis_figures folder, one should examine the plots named with (ACR=OFF). 


Please use one of the following for <os_name>: tizen, webos, roku_roku, roku_tcl, fire, smartcast

   python manager_analysis.py <os_name>

For Sony Google TV:

   python sony_manager_analysis.py google



## Limitations

Although we provide the automated control scripts for smart TVs, the hardware (smart TV) is required to test them. 
However, we provide our dataset, which helps to reproduce the results from our dataset.

## 📄 License

This project is licensed under the **Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International (CC-BY-NC-ND 4.0)**.

See [LICENSE] file for full details.

### What this means

You are free to:
- ✓ Share and use this work (academic and non-commercial)
- ✓ Give attribution to the authors

You may NOT:
- ✗ Use for commercial purposes
- ✗ Modify or create derivative works
- ✗ Distribute modified versions

For full details: https://creativecommons.org/licenses/by-nc-nd/4.0/

