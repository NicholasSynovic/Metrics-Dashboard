# TODO: Create a requirements.txt file
# TODO: Replace tqdm with progress
# TODO: Multithread what we can
# TODO: Replace branches, files, and language collectors with a version that
# runs off of the output of git-all-python
# TODO: Implement a better solution of git-all-python

from sqlite3 import Connection
import sys, os
from importlib import import_module

from tqdm import tqdm

from branches import Branches
from commits import Commits
from files import Files
from forks import Forks
from issues import Issues
from languages import Languages
from libs.cmdLineInterface import arguementHandling
from libs.databaseConnector import DatabaseConnector
from repository import Repository


class DataCollection:
    def __init__(
        self,
        oauthToken: str,
        outfile: str,
        url: str,
        username: str,
    ) -> None:
        self.file = outfile
        self.repository = url.split("/")[-1]
        self.url = url
        self.token = oauthToken
        self.username = username

        self.dbConnector = DatabaseConnector(databaseFileName=outfile)

    def checkForFile(self) -> Connection:
        self.dbConnector.createDatabase()
        self.dbConnector.openDatabaseConnection()

    def createFileTablesColumns(self, dbConnection: Connection) -> bool:

        branchesSQL = (
            "CREATE TABLE Branches (ID INTEGER, Name TEXT, SHA TEXT, PRIMARY KEY(ID))"
        )

        commitsSQL = "CREATE TABLE Commits (Commit_SHA TEXT, Branch TEXT, Author TEXT, Commit_Date TEXT, Tree_SHA TEXT, Comment_Count INTEGER, Lines_Of_Code INTEGER, Number_Of_Characters INTEGER, Size_In_Bytes INTEGER, PRIMARY KEY(Commit_SHA))"

        filesSQL = "CREATE TABLE Files (ID INTEGER, Commit_SHA TEXT, Branch TEXT, File_Tree TEXT, Status TEXT, Raw_URL TEXT, Lines_Of_Code INTEGER, Number_Of_Characters INTEGER, Added_Lines INTEGER, Removed_Lines INTEGER, Size_In_Bytes INTEGER, PRIMARY KEY(ID), FOREIGN KEY(Commit_SHA) REFERENCES Commits(Commit_SHA))"

        forksSQL = "CREATE TABLE Forks (ID TEXT, Name TEXT, Owner TEXT, Created_At_Date TEXT, Updated_At_Date TEXT, Pushed_At_Date TEXT, Size INTEGER, Forks INTEGER, Open_Issues INTEGER, PRIMARY KEY(ID))"

        issuesSQL = "CREATE TABLE Issues (ID INTEGER, Count INTEGER, Title TEXT, Author TEXT, Assignees TEXT, Labels TEXT, State TEXT, Created_At_Date TEXT, Updated_At_Date TEXT, Closed_At_Date TEXT, PRIMARY KEY(ID));"

        languagesSQL = "CREATE TABLE Languages (ID INTEGER, Language TEXT, Bytes_of_Code INTEGER, PRIMARY KEY(ID))"

        repositorySQL = "CREATE TABLE Repository (ID INTEGER, Name TEXT, Owner TEXT, Private TEXT, Fork TEXT, Created_At_Date TEXT, Updated_At_Date TEXT, Pushed_At_Date TEXT, Size INTEGER, Forks INTEGER, Open_Issues INTEGER, PRIMARY KEY(ID))"

        self.dbConnector.executeSQL(sql=branchesSQL, commit=True)
        self.dbConnector.executeSQL(sql=commitsSQL, commit=True)
        self.dbConnector.executeSQL(sql=filesSQL, commit=True)
        self.dbConnector.executeSQL(sql=forksSQL, commit=True)
        self.dbConnector.executeSQL(sql=issuesSQL, commit=True)
        self.dbConnector.executeSQL(sql=languagesSQL, commit=True)
        self.dbConnector.executeSQL(sql=repositorySQL, commit=True)

    def localCloneGitRepo(self) -> None:
        repo: str
        if self.url.find(".git") == -1:
            repo = self.url + ".git"
        else:
            repo = self.url

        programDir = os.path.dirname(os.path.realpath(__file__))

        srcDir = os.path.dirname(os.path.realpath(__file__)) + "/{}".format(
            self.repository
        )

        os.chdir(programDir)
        os.system("python3 git-all-python/git-all-python -u {} -s {}".format(repo, srcDir))

        pass

    def startDataCollection(self) -> None:
        def _collectData(collector) -> int or bool:
            data = collector.getData()
            collector.insertData(dataset=data[0])
            return collector.iterateNext(data[1])

        def _scrapeData(collector) -> int or bool:
            collector.insertData()
            return 0

        def _showProgression(collector, maxIterations: int) -> None:
            for iteration in tqdm(
                range(0, abs(maxIterations) - 1),
            ):
                _collectData(collector)

        databaseConnection = self.checkForFile()
        self.createFileTablesColumns(dbConnection=databaseConnection)

        branchCollector = Branches(
            dbConnection=self.dbConnector,
            oauthToken=self.token,
            repository=self.repository,
            username=self.username,
            url="https://api.github.com/repos/{}/{}/branches?per_page=100&page={}",
        )

        forksCollector = Forks(
            dbConnection=self.dbConnector,
            oauthToken=self.token,
            repository=self.repository,
            username=self.username,
            url="https://api.github.com/repos/{}/{}/forks?per_page=100&page={}",
        )

        issuesCollector = Issues(
            dbConnection=self.dbConnector,
            oauthToken=self.token,
            repository=self.repository,
            username=self.username,
            url="https://api.github.com/repos/{}/{}/issues?state=all&per_page=100&page={}",
        )

        languageCollector = Languages(
            dbConnection=self.dbConnector,
            oauthToken=self.token,
            repository=self.repository,
            username=self.username,
            url="https://api.github.com/repos/{}/{}/languages?per_page=100&page={}",
        )

        repositoryCollector = Repository(
            dbConnection=self.dbConnector,
            oauthToken=self.token,
            repository=self.repository,
            username=self.username,
            url="https://api.github.com/repos/{}/{}?per_page=100&page={}",
        )

        print("\nRepository Languages")
        languagePages = _collectData(languageCollector)  # One request only
        _showProgression(languageCollector, languagePages)

        print("\nRepository Information")
        repositoryPages = _collectData(repositoryCollector)  # One request only
        _showProgression(repositoryCollector, repositoryPages)

        print("\nRepository Branches")
        branchPages = _collectData(branchCollector)  # Estimated < 10 requests
        _showProgression(branchCollector, branchPages)

        print("\nRepository Forks")
        forkPages = _collectData(forksCollector)  # Estimated < 10 requests
        _showProgression(forksCollector, forkPages)

        print("\nRepository Issues")
        issuePages = _collectData(issuesCollector)  # Estimated < 20 requests
        _showProgression(issuesCollector, issuePages)

        commitsID = 0
        branchList = self.dbConnector.selectColumn(table="Branches", column="Name")
        for branch in branchList:
            print("\nRepository Commits from Branch {}".format(branch[0]))
            commitsCollector = Commits(
                dbConnection=self.dbConnector,
                id=commitsID,
                oauthToken=self.token,
                repository=self.repository,
                sha=branch[0],
                username=self.username,
                url="https://api.github.com/repos/{}/{}/commits?per_page=100&page={}&sha={}",
            )
            commitPages = _collectData(
                commitsCollector
            )  # Estimated to have the most requests
            _showProgression(commitsCollector, commitPages)
            commitsID = commitsCollector.exportID()

        # TODO: Implement a loading bar for the Files module
        # TODO: Reduce complexity where possible in the Files module

        # Creates a combined list of every commit paired with its corresponding     branch
        branchList = self.dbConnector.selectColumn(table="Commits", column="Branch")
        commitSHAList = self.dbConnector.selectColumn(
            table="Commits", column="Commit_SHA"
        )
        # https://www.geeksforgeeks.org/python-merge-two-lists-into-list-of-tuples/
        mergedList = tuple(zip(branchList, commitSHAList))

        filesID = 0
        for pair in mergedList:
            branch = pair[0][0]
            commit = pair[1][0]
            print(
                "\nRepository Files from Branch {} from Commit {}".format(
                    branch, commit
                )
            )
            filesCollector = Files(
                commitSHA=commit,
                branch=branch,
                dbConnection=self.dbConnector,
                id=filesID,
                repository=self.repository,
                username=self.username,
                url="https://github.com/{}/{}/commit/{}",
            )
            _scrapeData(filesCollector)
            filesID = filesCollector.exportID()


if __name__ == "__main__":
    cmdLineArgs = arguementHandling()

    dc = DataCollection(
        oauthToken=cmdLineArgs.token[0],
        outfile=cmdLineArgs.outfile[0],
        url=cmdLineArgs.url[0],
        username=cmdLineArgs.url[0].split("/")[-2],
    )

    dc.localCloneGitRepo()

    dc.startDataCollection()
