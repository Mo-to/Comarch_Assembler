import configparser
import logging
import os.path
import sys

import pandas as pd
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

config = configparser.ConfigParser()
config.read('config.ini')
SPREADSHEET_ID = config['DEFAULT']['SpreadsheetId']
CODE_RANGE = config['DEFAULT']['CodeRange']
PROGRAM_TEMPLATE_FILE_PATH = config['DEFAULT']['ProgramTemplate']
if len(sys.argv) == 4:
    INPUT_CODE_PATH, OUTPUT_CODE_PATH, PROGRAM_FILE_PATH = sys.argv[1], sys.argv[2], sys.argv[3]
else:
    INPUT_CODE_PATH, OUTPUT_CODE_PATH, PROGRAM_FILE_PATH = config['DEFAULT']['InputFile'], \
        config['DEFAULT']['OutputFile'], \
        config['DEFAULT']['ProgramOutput']


def read_code_df(spreadsheet_id: str, sheets_range: str):
    """
    Return values in a range of a spreadsheet as pandas df
    Triggers a login screen in browser if no token.json is present
    """
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('sheets', 'v4', credentials=creds)

        # Call the Sheets API
        values = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id,
                                                     range=sheets_range).execute().get('values', [])
        return pd.DataFrame(values)
    except HttpError as err:
        print(err)


def get_command_to_code_dict(df: pd.DataFrame):
    """
    Return a dict of command to 5-bit code
    """
    COMMAND_COL = 7

    command_to_code = {}
    for row in df[df[COMMAND_COL] != ''].itertuples():
        code_val_dec = int('000' + str(row[1]) + str(row[2]) + str(row[3]) + str(row[4]) + str(row[5]), 2)
        code_val_hex = f'{code_val_dec:x}'
        param_command = parse_command_definition(row[COMMAND_COL+1])  # Returns a dict with keys: command_name, params
        code_name = param_command.get('command_name')
        params = param_command.get('params')

        command_to_code[code_name] = {
            'code_val': code_val_hex,
            'param_num': len(params),
            'length': len(params) + 1,
            'params': params,
        }
    return command_to_code


def parse_command_definition(command: str):
    """
    Parse a command of type NAME <param1> <param2> ... <paramN>, e.g. JMP <addr> to a dict with keys:
    command_name: str
    params: list of str
    """
    command_name = command.split('<')[0]
    params = command.split('<')[1:]
    # Strip the brackets from the params
    params = [param[:-1] for param in params]
    return {
        'command_name': command_name,
        'params': params,
    }


def get_human_code(path: str):
    """
    Read in the file named path and return the human code as a string array separated by line.
    Also clears out comments and empty lines.
    :param path:
    :return:
    """
    with open(path, 'r') as f:
        code = f.read()
    code = code.replace('\t', '    ')
    code_list = code.split('\n')

    # Iterate over lines and remove comments
    for index, line in enumerate(code_list):
        code_list[index] = ''
        for character in line:
            if character != ';':
                code_list[index] += character
            else:
                break

    # Remove leading and trailing whitespaces
    for index, line in enumerate(code_list):
        code_list[index] = line.strip()

    # Remove empty lines
    code_list = list(filter(None, code_list))

    return code_list


def create_associated_storage(human_code: list[str], commands_dict: dict) -> tuple[dict, dict]:
    """
    Eine Zeile kann mit einer Adresse beginnen. Eine Adresse ist ein Name mit einem einen
    Doppelpunkt am Ende. Der Doppelpunkt gehört nicht zum Namen, sondern dient nur zur
    Erkennung.
    Eine Adresse steht entweder
    • für eine Sprungzielmarke, wenn ein Befehl folgt (die Adresse ist die Adresse des Befehls),
    • einer Variablendefinition, wenn der Pseudobefehl DB oder RESB folgt (die Adresse der
    Variablen),
    • eine Konstantendefinition, wenn der Pseudobefehl EQU folgt (keine Adresse).
    """
    # Find all lines that start with a address
    variables = dict()
    constants = dict()
    for index, line in enumerate(human_code):
        line_sep = line.split(' ')
        is_label = False
        label = None
        for token in line_sep:
            if token.endswith(':'):
                is_label = True
                label = token[:-1]
                break
        if is_label:
            line_without_label = line.replace(label + ':', '').strip()
            if 'DB' in line_without_label:
                variable_name = label  # 'counter'
                variable_value = line_without_label.replace('DB', '').strip()  # '0'
                variables[variable_name] = {'value': variable_value, 'type': 'DB'}
            elif 'RESB' in line_without_label:
                variable_name = label  # 'counter'
                variable_value = line_without_label.replace('RESB', '').strip()  # '0'
                variables[variable_name] = {'number': variable_value, 'type': 'RESB'}
            elif 'EQU' in line_without_label:
                constant_name = label  # 'counter'
                constant_value = line_without_label.replace('EQU', '').strip()  # '0'
                constants[constant_name] = {'number': constant_value, 'type': 'EQU'}
            else:
                # Check if label if followed by a known command, else throw error
                if parse_human_command(line_without_label, commands_dict) is not None:
                    constants[label] = {'address': index, 'type': 'JMP'}
                else:
                    raise Exception(f'Label {label} not used as variable, constant or address.')
    return constants, variables


def clear_addresses(code: list[str]) -> list[str]:
    """
    Remove all  addresses from the code
    """
    clear_code = []
    for index, line in enumerate(code):
        line_sep = line.split(' ')
        new_line = ''
        for token in line_sep:
            if not token.endswith(':'):
                # If not an address, add to new line
                new_line = new_line + ' ' + token
        new_line = new_line.strip()
        if new_line.startswith('DB') or new_line.startswith('RESB') or new_line.startswith('EQU'):
            break
        else:
            clear_code.append(new_line.strip())
    return clear_code


def create_address_space(variables: dict, human_code: list[str], commands_dict: dict):
    """
    Counts the length of the code and defines the address needed for the variables
    """
    counter = 0
    extended_variables = variables.copy()
    for line in human_code:
        human_command = parse_human_command(line, commands_dict)
        counter += commands_dict[human_command.get('command_name')].get('length')
    for variable_name in variables.keys():
        if variables.get(variable_name).get('type') == 'DB':
            extended_variables[variable_name]['address'] = hex(counter)
            counter += 1
        elif variables.get(variable_name).get('type') == 'RESB':
            extended_variables[variable_name]['address_start'] = hex(counter)
            counter += int(variables.get(variable_name).get('number'))
            extended_variables[variable_name]['address_end'] = hex(counter)
    return extended_variables


def create_hex_code(human_code: list[str], commands_dict: dict, constants: dict, variables: dict):
    """
    Create a hex code from the human code using command_to_code dict
    :param human_code:
    :param commands_dict:
    :return:
    """
    hex_code = []
    for line in human_code:
        if line == '':
            continue
        command_parsed = parse_human_command(line, commands_dict, constants, variables)
        if command_parsed is None:
            raise Exception(
                f'Command "{line}" not found in code defintion. Please check your code and definition in Google Sheets')
        command = command_parsed.get('command_name')
        param = command_parsed.get('param')
        code_hex = commands_dict[command].get('code_val')

        if code_hex is not None:
            hex_code.append(code_hex)
            if param is not None:
                hex_code.append(param)

    # Lambda to convert the hex codes from ['f', '0', '4', '5', 'd', '02'] to ['0f', '00', '04', '05', '0d', '02']
    hex_code_formatted = lambda lst: [hex(int(str(x), 16))[2:].zfill(2) for x in lst]
    return hex_code_formatted(hex_code)


def parse_human_command(human_command: str, commands_dict: dict, constants: dict = None, variables: dict = None):
    """
    Parse a command of type NAME <value1> <value2> ... <paramN>, e.g. JMP #01 to a dict.
    Parameters:
    human_command: dict
    """
    # YOU NEED TO CHECK FOR LOAD A and LOAD B first, because the command LOAD is a substring of LOAD A or LOAD B
    # Solution sort the commands by length and check for the longest first
    for command in sorted(commands_dict.keys(), key=len, reverse=True):
        if human_command.startswith(command):
            command_name = command
            code_val = commands_dict[command].get('code_val')
            param_raw = human_command.replace(command, '')
            if param_raw == '':
                param_raw = None
            if param_raw is not None:
                if param_raw.isnumeric(): # HAS TO CHECK IF PARAM IS HEX BYTE ? && CHECK VAR AND CONST FOR ADD, VAL, NUMBER. DIFFERENCE VAL AND NUMBER?
                    param = param_raw
                elif variables is not None and param_raw in variables.keys():
                    param = variables.get(param_raw).get('address')
                elif constants is not None and param_raw in constants.keys():
                    if 'address' in constants.get(param_raw).keys():
                        param = constants.get(param_raw).get('address')
                    else:
                        param = constants.get(param_raw).get('number')
                else:
                    if constants is not None or variables is not None:
                        raise Exception(
                            f'Parameter "{param_raw}" for command {command_name} is not numeric or a defined variable in {variables} or constant in {constants}')
                    else:
                        param = param_raw
            else:  # No parameter
                param = None
            return {
                'command_name': command_name,
                'code_val': code_val,
                'param': param,
            }


def parse_to_file(hex_code: list[str], path: str, seperator: str = '\n') -> None:
    """
    Parse the hex code to a file
    :param hex_code: list of hex codes
    :param path: path to file
    """
    with open(path, 'w') as f:
        f.write(seperator.join(hex_code))


def parse_to_program(hex_code: list[str], path: str) -> None:
    """
    Parse the hex code to a file useable by LogisimEvolution
    """
    with open(PROGRAM_TEMPLATE_FILE_PATH, 'r') as f:
        template = f.read()

    program = template
    for hex in hex_code:
        program = program.replace('<placeholder>', hex, 1)
    program = program.replace('<placeholder>', '00')

    with open(path, 'w+') as f:
        f.write(program)


if __name__ == '__main__':
    # Get code definitions from spreadsheet
    values = read_code_df(SPREADSHEET_ID, CODE_RANGE)
    commands_dict = get_command_to_code_dict(values)
    logging.info(f'Command definition from gsheet: {commands_dict}')

    # Read in raw human code with comments and empty lines removed
    human_code = get_human_code(INPUT_CODE_PATH)
    logging.info(f'Human code: {human_code}')

    # Create associated storage (parse addresses, variables and constants). First iteration of assembler
    constants, variables = create_associated_storage(human_code, commands_dict)
    logging.debug(f'Constants: {constants}')
    logging.debug(f'Variables: {variables}')

    # Clear addresses from code
    human_code = clear_addresses(human_code)
    logging.debug(f'Human code without addresses: {human_code}')

    # Create address space for variables
    variables = create_address_space(variables, human_code, commands_dict)
    logging.debug(f'Extended variables: {variables}')

    hex_code = create_hex_code(human_code, commands_dict, constants, variables)
    logging.info(f'Final hex-code: {hex_code}')
    parse_to_file(hex_code, OUTPUT_CODE_PATH)
    parse_to_program(hex_code, PROGRAM_FILE_PATH)
