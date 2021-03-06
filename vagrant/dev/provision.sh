#! /bin/bash
set -e

# variables
ESUSER="esdev"
VHOSTNAMES="es-host es-mongo es-proxy es-rabbitmq es-service"
ESMOUNTID="esrepo"
TMPDIR="/tmp/esinstall"
LOGDIR="/var/log/esinstall"
ESDIR="/opt/eskapade"
KTBRELEASE="3.5-Beta"
KTBDIR="/opt/KaveToolbox"
ANADIR="/opt/anaconda"
PYCHARMRELEASE="2017.2.1"
PYCHARMDIR="/opt/pycharm"

# log function
function log {
  echo "$(date +'%F %T %Z'): $@"
}

# set non-interactive front end
export DEBIAN_FRONTEND="noninteractive"

# create directories for software installation
mkdir -p "${TMPDIR}"
mkdir -p "${LOGDIR}"
cd "${TMPDIR}"

# set names of host machine
hostip=$(ip route | awk '/default/ { print $3 }')
log "associating host names \"${VHOSTNAMES}\" to IP address ${hostip}"
echo -e "${hostip} ${VHOSTNAMES}" >> /etc/hosts

# create ESKAPADE user
log "creating ${ESUSER} user (password \"${ESUSER}\")"
adduser --disabled-login --gecos "" "${ESUSER}"
echo "${ESUSER}:${ESUSER}" | chpasswd

# enable login as ESKAPADE user with key
log "authorizing key \"esdev_id_rsa\" for ${ESUSER}"
mkdir -p "/home/${ESUSER}/.ssh"
cat /vagrant/ssh/esdev_id_rsa.pub >> "/home/${ESUSER}/.ssh/authorized_keys"
chown -R "${ESUSER}":"${ESUSER}" "/home/${ESUSER}/.ssh/"
chmod -R go-rwx "/home/${ESUSER}/.ssh"

# set up mounting of ESKAPADE repository
mkdir -p "${ESDIR}"
echo "${ESMOUNTID} ${ESDIR} vboxsf rw,nodev,uid=$(id -u ${ESUSER}),gid=$(id -g ${ESUSER}) 0 0" >> /etc/fstab
echo "vboxsf" >> /etc/modules
sudo -u "${ESUSER}" ln -s "${ESDIR}" "/home/${ESUSER}/$(basename ${ESDIR})"

# update system
log "updating package manager"
apt-get -y update &> "${LOGDIR}/update.log"
log "upgrading system"
apt-get -y dist-upgrade &> "${LOGDIR}/dist-upgrade.log"
log "installing additional packages"
apt-get -y install python &> "${LOGDIR}/install.log"

# install KAVE Toolbox
log "installing KAVE Toolbox"
cd "${TMPDIR}"
wget -q "http://repos:kaverepos@repos.dna.kpmglab.com/noarch/KaveToolbox/${KTBRELEASE}/kavetoolbox-installer-${KTBRELEASE}.sh"
bash "kavetoolbox-installer-${KTBRELEASE}.sh" --node &> "${LOGDIR}/install-ktb.log"

# install additional packages
log "installing additional packages for Eskapade"
apt-get install -y --no-install-recommends mongodb-clients &> "${LOGDIR}/install-additional.log"

# install Eskapade Python requirements
log "installing Eskapade Python requirements"
"${ANADIR}/pro/bin/pip" install -r /vagrant/python/requirements.txt &> "${LOGDIR}/install-Python-requirements.log"
"${ANADIR}/pro/bin/conda" install -y django pymongo &>> "${LOGDIR}/install-Python-requirements.log"
"${ANADIR}/pro/bin/pip" install djangorestframework markdown django-filter celery cherrypy names jaydebeapi \
	&>> "${LOGDIR}/install-Python-requirements.log"

# source KAVE setup in both login and non-login shells (interactive)
mv /etc/profile.d/kave.sh "${KTBDIR}/pro/scripts/"
sed -i -e "s|/etc/profile\.d/kave\.sh|${KTBDIR}/pro/scripts/kave.sh|g" /etc/bash.bashrc

# install Python packages for ROOT
log "installing Python packages for ROOT"
cd "${TMPDIR}"
bash -c "source ${KTBDIR}/pro/scripts/KaveEnv.sh && pip install rootpy==0.9.1"\
    &> "${LOGDIR}/install-rootpy.log"

# install Histogrammar fixes for Spark
log "installing Histogrammar fixes"
cp /vagrant/histogrammar/*.py "${ANADIR}/pro/lib/python3.5/site-packages/histogrammar/primitives"/

# setup PyCharm environment
sed -e "s|PYCHARM_HOME_VAR|${PYCHARMDIR}/pro|g" /vagrant/pycharm/pycharm_env.sh >> "${KTBDIR}/pro/scripts/KaveEnv.sh"
mkdir -p "${PYCHARMDIR}"
ln -sfT "pycharm-community-${PYCHARMRELEASE}" "${PYCHARMDIR}/pro"

# install PyCharm
log "installing PyCharm in ${PYCHARMDIR}/pycharm-community-${PYCHARMRELEASE}"
cd "${TMPDIR}"
wget -q "https://download.jetbrains.com/python/pycharm-community-${PYCHARMRELEASE}.tar.gz"
tar -xzf "pycharm-community-${PYCHARMRELEASE}.tar.gz" --no-same-owner -C "${PYCHARMDIR}"

# install Lubuntu desktop
log "installing desktop environment"
apt-get -y install lubuntu-desktop &>> "${LOGDIR}/install-desktop.log"

# general configuration for ESKAPADE user
cp /vagrant/bash/bashrc "/home/${ESUSER}/.bashrc"
cat /vagrant/bash/bash_aliases >> "/home/${ESUSER}/.bash_aliases"
cp /vagrant/vim/vimrc "/home/${ESUSER}/.vimrc"

# clean up
cd /
rm -rf "${TMPDIR}"
