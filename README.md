# COMARCH Assembler
# Info für Dr. Förster
- Das Programm befindet sich in einem öffentlichen Repository auf GitHub, folgen Sie der Installationsanleitung um das Repository zu clonen.
- Das Programm benötigt eine Datei "credentials.json" um auf die Google Sheets API zugreifen zu können. Diese Datei ist nicht im Repository enthalten, da sie sensible Daten enthält. Sie ist Teil dieser zip-Datei. Fügen Sie sie nach dem clonen des Repositories dem root-Verzeichnis hinzu.
- Das Programm nutzt die Google Sheets API um die Maschinencodes aus einer Google Tabelle zu lesen. Die genutzte Tabelle wurde für den Computer aus Labor 4 entwickelt, ist öffentlich zugänglich und kann hier eingesehen werden: https://docs.google.com/spreadsheets/d/1s8AJut2VmPQW_sHFVFF5YNUYHAidIszT0DfoOAU7YqU/edit?usp=sharing
- Das Beispielprogramm heißt "Fibonacci.a" und produziert den Maschinencode "Fibonacci_code.hex" und das Programm "Fibonacci_program.hex" zum Einlesen in LogiSimEvolution.

# Requirements
* Python >3.6 (tested on 3.11)

# Installation
Clone the repository:  
```git clone git@github.com:Mo-to/Comarch_Compiler.git```  

Optional: Create virtual environment (Recommended!):  
```python -m venv venv```  

Activate virtual environment (if created):
On Linux: ```source venv/bin/activate```  
On Windows: ```venv\Scripts\activate.bat```  

Install requirements:
```pip install -r requirements.txt```

# Preparations:
Open config.ini and: 
1. Change SpreadsheetId to the ID of the spreadsheet you want to use. You can find the ID of the Spreadsheet in the URL of the spreadsheet: ```https://docs.google.com/spreadsheets/d/<SpreadsheetId>```.
2. Change the CodeRange to the range in the sheet, where the machine code for the assembler commands is defined

Make sure the sheet has the following structure:

| Bit 0 | Bit 1 | Bit 2 | Bit 3 | Bit 4 | / | / | 7   | Microcode 0 | Microcode n | Microcode 23 |
|-------|-------|-------|-------|-------|---|---|-----|-------------|-------------|--------------|
| 0     | 0     | 0     | 0     | 0     | / | / | NOP | 0           | ...         | -            |  
| 0     | 0     | 0     | 1     | 0     | / | / |     | 0           | ...         | 1            |  
| 0     | 0     | 1     | 0     | 0     | / | / |     | -           | ...         | -            |  

The first 5 columns within the defined range (index 0-5) will be used for the hex code. Column 5 and 6 are irrelevant.
The name of the assembler command *need* to be in column 7. This behavior cannot be changed.  
The given [Spreadsheet](https://docs.google.com/spreadsheets/d/1s8AJut2VmPQW_sHFVFF5YNUYHAidIszT0DfoOAU7YqU) can be used as a template.

# Usage
## Command line:
Create hex file (<output_file>) and program file (<output_program_file>) from assembly file (<input_file>):  
```python assembler.py <input_file> <output_file> <output_program_file>```

## Use config.ini:
If no parameters are passed:  
```python assembler.py```  
or the wrong number of parameters is passed, the program uses the defaults defined in the ```config.ini```.