import yaml
import os
import logging
import subprocess
import socket
import sys
import docker
from time import sleep
import re
import smtplib

sep = os.sep
SETTINGS_PATH = os.environ['SETTINGS_PATH'] = os.path.abspath('settings.yml')
with open(SETTINGS_PATH, 'r') as f:
    SETTINGS = yaml.safe_load(f)

GIT_FLAG = SETTINGS['PGSettings']['IsGit']
BASE_PATH = SETTINGS['BasePath']
ARTEFACTS_PATH = SETTINGS['ArtefactsPath']
PG_SOURCE = SETTINGS['PGSettings']['PGsource']
PGPRO_REPO = SETTINGS['PGSettings']['PGsource'].split(os.sep)[-1]
BRANCHES = SETTINGS['PGSettings']['Branches']
LOGFILE = SETTINGS['BasePath']+f'{sep}fuzz.log'
GIT_CLEAN = f'git -C {PG_SOURCE} clean -xdf'
SQUIRREL_TIMEOUT = SETTINGS['SquirrelTimeout']
CHECK_TIMEOUT = SETTINGS['CheckTimeout']
GIT_COMPRESS = f'tar --exclude .git -zcf postgres.tar.gz --directory={PG_SOURCE} .'
COMPRESS = f'tar -zcf postgres.tar.gz --directory={PG_SOURCE} .'
EMAILSENDER = SETTINGS['Email']['senderlogin']
EMAILPASS = SETTINGS['Email']['senderpassword']
EMAILRECIEVERS = SETTINGS['Email']['receivers'].split(',')
HOSTING = SETTINGS['Email']['hosting']
EMAIL_PORT = SETTINGS['Email']['port']
local_ip = (([ip for ip in socket.gethostbyname_ex(socket.gethostname())[2] if not ip.startswith("127.")] or [[(s.connect(("8.8.8.8", 53)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]]) + ["no IP found"])[0]
test_env = os.environ.copy()
client = docker.from_env()


if sys.version_info[0] == 3:
    if sys.version_info[1] > 8:
        logging.basicConfig(filename=LOGFILE, encoding='utf-8',
                            level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    else:
        logging.basicConfig(filename=LOGFILE,
                            level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
else:
    sys.exit('How do you even get there?!')

    
def append_to_containers_list(container_name: str):
    with open(f'{BASE_PATH}{sep}containers', 'a') as f:
        f.write(f'{container_name}\n')


def send_mail(email_receivers: list, email_message: str, hosting: str, port: int):
    sender = EMAILSENDER
    sender_password = EMAILPASS
    mail_con = smtplib.SMTP_SSL(hosting, port)
    mail_con.login(sender, sender_password)
    for to_item in email_receivers:
        msg = 'From: %s\r\nTo: %s\r\nContent-Type: text/plain; charset="utf-8"\r\nSubject: %s\r\n\r\n' % (
        sender, to_item, 'PgPro GenFuzz reuslts')
        msg += email_message
        mail_con.sendmail(sender, to_item, msg.encode('utf8'))
    mail_con.quit()


def run_subproc(cmd: str, msg: str, env=test_env):
    logging.info(msg)
    res = subprocess.run(cmd.split(), env=env, capture_output=True, text=True)
    if res.stderr:
        logging.error(f'[!] {res.stderr}')


def check_git_repo(branch: str):
    GIT_CHECK1 = f'git -C {PG_SOURCE} branch -a'
    GIT_CHECK2 = f'grep -E {branch}$'
    branches = subprocess.run(GIT_CHECK1.split(' '), capture_output=True, check=True)
    res = subprocess.run(GIT_CHECK2.split(), input=branches.stdout, capture_output=True)
    if branches.stderr:
        sys.exit('[!] This is not a git repo! Check the yml config!')
    if not res.stdout:
        sys.exit(f'[!] There is no such branch in the repository')


def prepare_source(branch: str):
    run_subproc("rm -f postgres.tar.gz", f'Delete old tarball')
    GIT_CHECKOUT = f'git -C {PG_SOURCE} checkout {branch}'
    if GIT_FLAG:
        check_git_repo(branch)
        run_subproc(GIT_CHECKOUT, f'[+] Checkout to {branch}')
        run_subproc(GIT_CLEAN, f'[+] Clean up old build artefacts')
        run_subproc(GIT_COMPRESS, f'[+] Compressing the source repo')
    else:
        run_subproc(COMPRESS, f'[+] Compressing the source repo')
    

def start_sqlancer(branch: str, context=BASE_PATH) -> bool:
    try:
        client.images.get(f"sqlancer:pg-{branch}")
        logging.debug('[*] Docker image was found! Initializing...')
    except docker.errors.ImageNotFound:
        logging.debug('[*] Waiting for image build ...')
        try:
            client.images.build(path=context, dockerfile=f'{context}{sep}sqlancer{sep}dockerfile',
                            tag=f'sqlancer:pg-{branch}', rm=True)
        except docker.errors.BuildError as e:
            if 'mvn package -DskipTests' in str(e):
                client.images.build(path=context, dockerfile=f'{context}{sep}sqlancer{sep}dockerfile',
                            tag=f'sqlancer:pg-{branch}', rm=True)
            else:
                logging.error(f'[!] Check if this version of postgres is compatible with sqlancer. Minimal version is 13. In other cases you should check folders and scripts structure in {BASE_PATH}.\n Here the exception occured:\n {e}')
                return False
        logging.debug('[*] The build is done. Let is roll!')
    client.containers.run(f'sqlancer:pg-{branch}', name=f'pg-{branch}',
                          stdin_open=True, 
                          detach=True, 
                          privileged=True,
                          environment={"BRANCH": branch},
                          volumes={f'{ARTEFACTS_PATH}': {'bind': '/opt/arts', 'mode': 'rw'}})
    append_to_containers_list(f'sqlancer-{branch}')
    logging.info(f'[+] A container with sqlancer and postgres-{branch} has successfully started. Name of the container is sqlancer-{branch}')
    return True


def start_squirrel(branch: str, context=BASE_PATH) -> bool:
    try:
        client.images.get(f"squirrel:pg-{branch}")
        logging.debug('[*] Docker image was found! Initializing...')
    except docker.errors.ImageNotFound:
        logging.debug('[*] Waiting for image build ...')
        try:
            client.images.build(path=context, dockerfile=f'{context}{sep}squirrel{sep}dockerfile',
                            tag=f'squirrel:pg-{branch}', rm=True)
        except docker.errors.BuildError as e:
            logging.error(f'[!] You should check folders and scripts structure in {BASE_PATH}.\n Here the exception occured:\n {e}')
            # sys.exit(f'[!] Error with squirrel build. See the {LOGFILE} for detailed explanation')
            return False
        logging.debug('[*] The build is done. Let is roll!...')
    client.containers.run(f'squirrel:pg-{branch}', 
                          name=f'squirrel-{branch}', 
                          stdin_open=True, 
                          detach=True,
                          environment={"TIMEOUT": SQUIRREL_TIMEOUT,
                                       "BRANCH": branch},
                          volumes={f'{ARTEFACTS_PATH}': {'bind': '/opt/arts', 'mode': 'rw'}})
    append_to_containers_list(f'squirrel-{branch}')
    logging.info(f'[+] A container with squirrel and pg-{branch} has started successfully. Name of the container is squirrel-{branch}')
    return True


def check_squirrel(containers: list) -> bool:
    for container in containers:
        if container.startswith('squirrel'):
            return True
    return False


def main():  
    run_subproc(f'git -C {PG_SOURCE} pull', f'[+] Pulling the source repo')
    for branch,_ in BRANCHES.items():
        prepare_source(branch)
        sqlancer_status = start_sqlancer(branch)
        squirrel_status = start_squirrel(branch)
        if sqlancer_status:
            logging.info('[+] Sqlancer fuzzing started succesfully')
        if squirrel_status:
            logging.info('[+] Squirrel fuzzing started succesfully')
    run_subproc("rm -f postgres.tar.gz", f'[+] Delete old tarball')
    with open('containers', 'r') as f:
        containers = f.read().splitlines()
    squirrel_flag = False
    while True:
        if containers:
            artefacts = [art[:-7] for art in os.listdir(ARTEFACTS_PATH)]
            artefacts = [art[:art.find('{')]+art[art.rfind('}')+2:] for art in artefacts]
            logging.info('[+] list of available containers: ' + str(containers))
            logging.info('[+] list of available artefacts: ' + str(artefacts))
            for art in artefacts:
                if art in containers:
                    # client.containers.get(art).stop()
                    # client.containers.get(art).remove()
                    # logging.info(f'[+] Container {art} has been stopped and removed')
                    if 'sqlancer' in art:
                        send_mail(EMAILRECIEVERS, f'Sqlancer session for pg-{branch} has been finished.\nArtefacts can be obtained on the {local_ip} machine in the folder {ARTEFACTS_PATH}', HOSTING, int(EMAIL_PORT))
                    containers.remove(art)
            if not squirrel_flag and containers and not check_squirrel(containers):
                send_mail(EMAILRECIEVERS, f'Squirrel fuzzing is done!\nArtefacts can be obtained on the {local_ip} machine in the folder {ARTEFACTS_PATH}.', HOSTING, int(EMAIL_PORT))
                squirrel_flag = True
            sleep(CHECK_TIMEOUT)
        else:
            artefacts = [art+'\n' for art in os.listdir(ARTEFACTS_PATH)]
            artefacts_str = ''.join(artefacts)
            send_mail(EMAILRECIEVERS, f"The artefacts path specified in the settings is: {local_ip}:{ARTEFACTS_PATH}\nObtained artefacts:\n {artefacts_str}", HOSTING, int(EMAIL_PORT))
            os.remove('containers')
            break


main()