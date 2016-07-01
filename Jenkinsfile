#!groovy
// -*- mode: Groovy;-*-
// Jenkinsfile ---
//
// Filename: Jenkinsfile
// Description:
// Author: Elric Milon
// Maintainer:
// Created: Thu Jun  9 14:11:55 2016 (+0200)

// Commentary:
//
//
//
//

// Change Log:
//
//
//
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or (at
// your option) any later version.
//
// This program is distributed in the hope that it will be useful, but
// WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
// General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with GNU Emacs.  If not, see <http://www.gnu.org/licenses/>.
//
//

// Code:

def power_users = ["whirm"]
def change_author

//////////////////
def failFast = true
def skipTests = false
def skipExperiments = false
//////////////////


stage "Verify author"

node {
  change_author = env.CHANGE_AUTHOR
}

def changeGHStatus(message) {
  node {
    // TODO: None of this seem to work at the time of writing.
    //step([$class: 'GitHubCommitStatusSetter', contextSource: [$class: 'ManuallyEnteredCommitContextSource', context: 'Jenkins'], statusResultSource: [$class: 'ConditionalStatusResultSource', results: [[$class: 'AnyBuildResult', message: message, state: 'PENDING']]]])
    //step([$class: 'GitHubCommitStatusSetter', statusResultSource: [$class: 'ConditionalStatusResultSource', results: [[$class: 'AnyBuildResult', message: message, state: 'PENDING']]]])
    //step([$class: 'GitHubCommitNotifier', resultOnFailure: 'FAILURE', statusMessage: [content: message]])
    //step([$class: 'GitHubSetCommitStatusBuilder', statusMessage: [content: message]])
  }
}

echo "Changeset from ${change_author}"
if (power_users.contains(change_author)) {
  echo "PR comes from power user. Testing"
} else {
  changeGHStatus('Waiting for organization member aproval')
  input "Do you want to test this change by '${change_author}'?"
  changeGHStatus('Job execution approved, going forth!')
}




def gitCheckout(url, branch, targetDir=''){
  if (targetDir == '') {
    targetDir = (url =~ '.*/(.+).git')[0][1]
  }
  echo "cloning ${url} to ${targetDir} and checking out branch: ${branch}"

  checkout([$class: 'GitSCM',
            userRemoteConfigs: [[url: url]],
            branches: [[name: branch]],

            doGenerateSubmoduleConfigurations: false,
            extensions: [[$class: 'CloneOption',
                          noTags: false,
                          reference: '',
                          shallow: true],

                         [$class: 'SubmoduleOption',
                          disableSubmodules: false,
                          recursiveSubmodules: true,
                          reference: '',
                          trackingSubmodules: false],

                         [$class: 'RelativeTargetDirectory',
                          relativeTargetDir: targetDir],

                         [$class: 'CleanCheckout'],

                         [$class: 'CleanBeforeCheckout']],
            submoduleCfg: [],
           ])

}

def checkoutGumby() {
  gitCheckout('https://github.com/tribler/gumby.git', '*/devel')
}

def unstashAll() {
  unstash 'tribler'
  unstash 'gumby'
  dir('tribler/Tribler/'){
    unstashDispersy()
  }
}

def unstashDispersy() {
  unstash 'dispersy'
  sh 'tar xpf dispersy.tar ; rm dispersy.tar'
}


def runTestsAndStash(testRunner, stashName) {
  try {
    testRunner()
  } finally {
    stash includes: 'output/**', name: "${stashName}"
  }
}

def unstashAllResults() {
  dir('output'){
    dir('dispersy_osx_results'){
      unstash 'dispersy_osx_results'
    }
    dir('dispersy_win32_results'){
      unstash 'dispersy_win32_results'
    }
    dir('dispersy_results'){
      unstash 'dispersy_results'
    }
    dir('dispersy_tribler_results'){
      unstash 'dispersy_tribler_results'
    }
  }
}

def runDispersyTestsOnOSX = {
  deleteDir()
  unstashDispersy()
  unstash 'gumby'
  sh '''
WORKSPACE=$PWD
OUTPUT=$WORKSPACE/output
mkdir -p $OUTPUT

export PATH=$PATH:~/Library/Python/2.7/bin

#NOSE_EXTRAS="--cover-html --cover-html-dir=$WORKSPACE/output/coverage/ --cover-branches -d"
NOSECMD="nosetests -x -v --with-xcoverage --with-xunit --all-modules --traverse-namespace --cover-package=dispersy  --cover-inclusive"

$NOSECMD --xcoverage-file=$OUTPUT/coverage.xml --xunit-file=$OUTPUT/nosetests.xml --xunit-testsuite-name=OSX_dispersy   dispersy/tests

# TODO: make a gumby job to parallelize the dispersy test execution
# env
# export TMPDIR="$PWD/tmp"
# export NOSE_COVER_TESTS=1
# export GUMBY_nose_tests_parallelisation=12
# export NOSE_TESTS_TO_RUN=dispersy/tests
# export PYTHONPATH=$HOME/.local/lib/python2.7/site-packages:$PYTHONPATH
# export PYLINTRC=$PWD/tribler/.pylintrc
# ulimit -c unlimited
# gumby/run.py gumby/experiments/tribler/run_all_tests_parallel.conf
'''
}

def runDispersyTestsOnLinux = {
  deleteDir()
  unstashDispersy()
  sh '''
#cd tribler/Tribler/

WORKSPACE=$PWD
OUTPUT=$WORKSPACE/output
mkdir -p $OUTPUT
#NOSE_EXTRAS="--cover-html --cover-html-dir=$WORKSPACE/output/coverage/ --cover-branches -d"
NOSECMD="nosetests -x -v --with-xcoverage --with-xunit --all-modules --traverse-namespace --cover-package=dispersy  --cover-inclusive"

$NOSECMD --xcoverage-file=$OUTPUT/coverage.xml --xunit-testsuite-name=Linux_dispersy dispersy/tests/

# TODO: make a gumby job to parallelize the dispersy test execution
# env
# export TMPDIR="$PWD/tmp"
# export NOSE_COVER_TESTS=1
# export GUMBY_nose_tests_parallelisation=12
# export NOSE_TESTS_TO_RUN=dispersy/tests
# export PYTHONPATH=$HOME/.local/lib/python2.7/site-packages:$PYTHONPATH
# export PYLINTRC=$PWD/tribler/.pylintrc
# ulimit -c unlimited
# gumby/run.py gumby/experiments/tribler/run_all_tests_parallel.conf
'''
}

def runDispersyTestsOnWindows32 = {
  deleteDir()
  unstashDispersy()
  sh '''
PATH=/usr/bin/:$PATH
WORKSPACE=$PWD
# get the workspace as windows path
UNIX_WORKSPACE=$(cygpath -u $WORKSPACE)
export OUTPUT_DIR=$WORKSPACE\\output
mkdir -p $UNIX_WORKSPACE/output

WORKSPACE=$PWD
OUTPUT=$WORKSPACE/output
mkdir -p $OUTPUT
#NOSE_EXTRAS="--cover-html --cover-html-dir=$WORKSPACE/output/coverage/ --cover-branches -d"
NOSECMD="nosetests -x -v --with-xcoverage --with-xunit --all-modules --traverse-namespace --cover-package=dispersy  --cover-inclusive"

$NOSECMD --xcoverage-file=$OUTPUT/coverage.xml --xunit-testsuite-name=Win32_dispersy dispersy/tests/

'''
}

def runTriblerTestsOnLinux = {
  deleteDir()
  unstashAll()
  sh '''
export TMPDIR="$PWD/tmp"
export NOSE_COVER_TESTS=1
export GUMBY_nose_tests_parallelisation=12
export PYTHONPATH=$HOME/.local/lib/python2.7/site-packages:$PYTHONPATH
export PYLINTRC=$PWD/tribler/.pylintrc
ulimit -c unlimited
gumby/run.py gumby/experiments/tribler/run_all_tests_parallel.conf
'''
}

stage "Checkout"

parallel "Checkout Tribler without dispersy": {
  node {
    deleteDir()
    gitCheckout('https://github.com/tribler/tribler.git', '*/devel')

    dir('tribler') {
      // TODO: this shouldn't be necessary, but the git plugin gets really confused
      // if a submodule's remote changes.
      sh 'git submodule update --init --recursive'
    }
    stash includes: '**', excludes: 'tribler/Tribler/dispersy', name: 'tribler'
  }
},
"Checkout Gumby": {
  node {
    deleteDir()
    checkoutGumby()
    stash includes: '**', name: 'gumby'
  }
},
"Checkout dispersy": {
  node {
    dir('dispersy'){
      deleteDir()
      checkout scm
      // TODO: this shouldn't be necessary, but the git plugin gets really confused
      // if a submodule's remote changes.
      sh 'git submodule update --init --recursive'
      sh 'sed -i s/asdfasdf// tests/__init__.py' // Unbreak the tests
    }
    // TODO: For some reason it's impossible to stash any .git file, so work around it.
    sh 'tar cpf dispersy.tar dispersy'
    stash includes: 'dispersy.tar', name: 'dispersy'
  }
},
failFast: failFast


stage "Tests"
try {
  if (! skipTests) {
    parallel "Linux dispersy tests": {
      node {
        runTestsAndStash(runDispersyTestsOnLinux, 'dispersy_results')
      }
    },
    "Linux Tribler tests": {
      node {
        runTestsAndStash(runTriblerTestsOnLinux, 'dispersy_tribler_results')
      }
    },
    "OSX dispersy tests": {
      node("osx") {
        runTestsAndStash(runDispersyTestsOnOSX, 'dispersy_osx_results')
      }
    },
    "Windows 32 dispersy tests": {
      node("win32") {
        runTestsAndStash(runDispersyTestsOnWindows32, 'dispersy_win32_results')
      }
    },
                    failFast: failFast
  }
} finally {
  // stage "Publish test results"
  if (! skipTests) {
    node {
      deleteDir()
      sh 'mkdir -p output/dispersy_osx_results'
      unstashAllResults()
      archive '**' // TODO: This should be done only in case of failure, the actual archiving should be done at the very end.
      step([$class: 'JUnitResultArchiver', testResults: '**/*nosetests.xml'])
      // step([$class: 'JUnitResultArchiver',
      //       testDataPublishers: [[$class: 'TestDataPublisher']],
      //       healthScaleFactor: 1000,
      //       testResults: '**/*nosetests.xml'])
    }
  }
}

stage "Coverage"
if (! skipTests) {
  node {
    unstashDispersy()
    unstashAllResults()
    sh '''
set -x
echo $PATH
export PATH=$PATH:$HOME/.local/bin/

OUTPUT=$PWD/output/cover
mkdir -p $OUTPUT

cd dispersy

diff-cover `find $OUTPUT/.. -iname coverage.xml` --compare-branch origin/$CHANGE_TARGET --fail-under 100 --html-report $OUTPUT/index.html --external-css-file $OUTPUT/style.css
'''
    dir('output/cover') {
      publishHTML(target: [allowMissing: false, alwaysLinkToLastBuild: false, keepAll: true, reportDir: '.', reportFiles: 'index.html', reportName: 'Coverage diff'])
    }
  }
}

//stage "Experiments"
if (! skipExperiments) {
  node('master') {
    deleteDir()
    unstashAll()
    stash "experiment_workdir"
    withEnv(['EXPERIMENT_CONF=gumby/experiments/dispersy/allchannel.conf']){
      load "gumby/scripts/jenkins/run_experiment_in_free_cluster.groovy"
    }
  }
}

stage "Style and static analysis"
parallel "Pylint": {
  node {
    deleteDir()
    unstashDispersy()

    sh '''
export PATH=$PATH:$HOME/.local/bin/

mkdir -p output

cd dispersy

ls -la

#git branch -r
#(git diff origin/${CHANGE_TARGET}..HEAD | grep ^diff)||:

PYLINTRC=.pylintrc diff-quality --violations=pylint --options="dispersy" --compare-branch origin/${CHANGE_TARGET} --fail-under 100 --html-report ../output/index.html --external-css-file ../output/style.css
'''
    dir('output') {
      publishHTML(target: [allowMissing: false, alwaysLinkToLastBuild: false, keepAll: true, reportDir: '.', reportFiles: 'index.html', reportName: 'Code quality diff'])
    }
  }
},
failFast: failFast

stage "Rogue commit checks"
node {
  deleteDir()
  unstashDispersy()
  sh '''
cd dispersy

ROGUE_COMMITS=$(git log -E --grep=\'^(DROPME|fixup!|Merge)\' origin/${CHANGE_TARGET}..HEAD)

if [ ! -z "${ROGUE_COMMITS}" ]; then
echo "Found some bad commits:"
echo $ROGUE_COMMITS
exit 1
fi
'''
}

//
// Jenkinsfile ends here
