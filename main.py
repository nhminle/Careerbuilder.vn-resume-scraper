import sys
import os
import shutil
from PyQt5 import QtWidgets
from PyQt5.uic import loadUi
from PyQt5.QtWidgets import *
import requests
from bs4 import BeautifulSoup
import xlsxwriter
import pandas as pd
import numpy as np
import datetime as dt

url = 'https://careerbuilder.vn/vi/employers/login'
data = {
    'username': '',
    'password': ''
}
with requests.session() as sess:
    sess.post(url, data)
    source = sess.get('https://careerbuilder.vn/vi/tim-ung-vien.html').text
    soup = BeautifulSoup(source, 'lxml')
    field_list = soup.find_all('div', class_='col-md-12')

    class WelcomeScreen(QWidget):
        def __init__(self):
            super(WelcomeScreen, self).__init__()
            loadUi('loginscreen.ui', self)
            self.login_button.clicked.connect(self.gotomain)

        def gotomain(self):
            data['username'] = self.line_username.text()
            data['password'] = self.line_password.text()
            if BeautifulSoup(sess.post(url, data).text, 'lxml').find('em', class_='fa fa-sign-out') is None:
                self.label_3.setText('Tên đăng nhập/Mật khẩu không chính xác. Vui lòng thử lại')
            else:
                main = main_screen()
                widget.addWidget(main)
                widget.setCurrentIndex(widget.currentIndex() + 1)

    list_of_jobs = []
    class main_screen(QWidget):
        def __init__(self):
            super(main_screen, self).__init__()
            loadUi('main.ui', self)
            for fields in field_list:
                self.comboBox_field.addItem(fields.p.text)
            self.button_field.clicked.connect(self.button_field_pressed)
            self.button_job.clicked.connect(self.button_job_pressed)
            self.button_confirm.clicked.connect(self.button_confirm_pressed)

        def button_confirm_pressed(self):
            # Get value from field
            Major = self.comboBox_field.currentText()
            Job = self.comboBox_job.currentText()
            Year = str(self.slider_yearexp.value())
            Comparison = self.comboBox_compare.currentText()

            text_message = "Bạn đang chọn ngành '{0}' có danh mục nghề là '{1}' với các ứng viên có số năm kinh nghiệm {2} {3} năm!\n Nếu đồng ý vui lòng nhấn nút xuất file".format(Major,Job,Comparison,Year)
            self.label_Information.setText(text_message)


        def button_field_pressed(self):
            self.comboBox_job.clear()
            for jobs in field_list[self.comboBox_field.currentIndex()].find_all('a'):
                self.comboBox_job.addItem(jobs.text)
                list_of_jobs.append(jobs)

        def button_job_pressed(self):
            # Init variables
            Year = int(self.slider_yearexp.value())
            candidate_info_list_list = []
            candidate_pdf_list_list = []
            table_info = []
            index_comparison = self.comboBox_compare.currentText()

            # Set flag comparison
            if index_comparison == 'Trên':
                flag_compare = 1
            elif index_comparison == 'Dưới':
                flag_compare = 2
            else:
                flag_compare = 0

            print("Processing....")

            # set excel file name
            excel_file_name = list_of_jobs[self.comboBox_job.currentIndex()].text.replace('/', 'hoặc')
            # get list of candidate
            source2 = sess.get(list_of_jobs[self.comboBox_job.currentIndex()]['href']).text
            soup2 = BeautifulSoup(source2, 'lxml')
            list_of_candidates = soup2.find_all('div', 'job-name')
            list_of_candidates.pop(0)

            # get table of candidates
            table = soup2.find('div', 'table table-jobs-posting').find_all('td')
            dfTable =  pd.DataFrame(table)

            # Set index for columns
            col_index = [1,2,3,4,5,6]
            dfTable['Row_ID'] = np.tile(col_index, len(dfTable) // len(col_index)).tolist() + col_index[:len(dfTable)%len(col_index)]

            # Select 2nd columns (Số năm kn trong table)
            dfColumn = dfTable.loc[dfTable['Row_ID'] == 2]

            # Split Year column
            dfColumn[['col1','col2','col3']] = pd.DataFrame(dfColumn[0].tolist(), index= dfColumn.index)
            dfYearExp = dfColumn[['col2']]
            dfYearExp = pd.Series(dfColumn['col2'],name='YearExp').to_frame()

            # Split Year in Array
            dfTemp = pd.DataFrame(dfYearExp['YearExp'].values.tolist(), index=dfYearExp.index)
            splitString = dfTemp[0].str.split(' ')
            list_year = []
            for item in splitString:
                if item[0] == 'Trên':
                    list_year.append(item[1])
                elif item[0] == 'Chưa':
                    list_year.append(0)
                else:
                    list_year.append(item[0])

            # Convert list to Dataframe
            dfCandidateYearExp = pd.DataFrame(list_year,columns=['Year_Experience'])


            # go to each candidate's page and scrape info
            for candidates in list_of_candidates:
                source2 = sess.get(candidates.find('a')['href']).text
                soup2 = BeautifulSoup(source2, 'lxml')
                candidate_info_list = []
                candidate_pdf_list = []
                try:
                    info = soup2.find('ul', class_='info-list').find_all('p')
                    pdf = soup2.find('li', class_='exportpdf').find_all(href=True)
                except:
                    pass
                for i in info:
                    if info.index(i) % 2 == 0:
                        pass
                    else:
                        candidate_info_list.append(i.text)

                for y in pdf:
                    candidate_pdf_list.append((y['href']))

                candidate_info_list_list.append(candidate_info_list)
                candidate_pdf_list_list.append(candidate_pdf_list)


            # Convert list to Dataframe
            dfCandidateInfo = pd.DataFrame(candidate_info_list_list,columns=['Full_Name','DoB','Nationality','Status','Country','Province','District'])
            dfCandidatePDF= pd.DataFrame(candidate_pdf_list_list,columns=['PDF'])

            # Merge 3 dataframes
            frames = [dfCandidatePDF, dfCandidateInfo, dfCandidateYearExp]
            dfCandidate = pd.concat(frames, axis=1, join="outer", ignore_index=True)
            dfCandidate.columns =['PDF','Full_Name','DoB','Nationality','Status','Country','Province','District','Year_Experience']
            dfCandidate['Year_Experience'] = dfCandidate['Year_Experience'].astype(int)

            # Filter dataframe with condition from slider
            if flag_compare == 1:
                dfCandidate = dfCandidate.loc[dfCandidate['Year_Experience'] > Year]
                print('cond1')
            elif flag_compare == 2 :
                dfCandidate = dfCandidate.loc[dfCandidate['Year_Experience'] < Year]
                print('cond2')
            elif flag_compare == 0 :
                dfCandidate = dfCandidate.loc[dfCandidate['Year_Experience'] == Year]
                print('cond3')


            # ---------- EXPORT PDF and FILE -----------
            # directory = 'D:/PythonApp/'
            #
            # print('Exporting pdf file...')
            # # Check href link or not
            # dfCandidate['Flag'] = dfCandidate['PDF'].str.contains('https', regex=False)
            #
            #
            # # Loop datafram candidate for identifying href link to download
            # for index, row in dfCandidate.iterrows():
            #     if row['Flag'] == True:
            #         # Get response object for link
            #         link = str(row['PDF'])
            #         response = requests.get(link, allow_redirects=True)
            #
            #         # Write content in pdf file
            #         export_pdf_path = '{0}{1}.pdf'.format(directory,str(row['Full_Name']))
            #         pdf = open(export_pdf_path,'wb')
            #         pdf.write(response.content)
            #         pdf.close()
            #
            #
            # print('Exporting excel file...')
            # # Export to excel by pandas
            # export_file_path = '{0}list_candidates_{1}.xlsx'.format(directory,excel_file_name)
            # dfExport = dfCandidate[['Full_Name','DoB','Nationality','Status','Country','Province','District','Year_Experience']]
            # dfExport.to_excel(export_file_path,sheet_name='Candidate')


            print('Completed')

            # new_workbook = xlsxwriter.Workbook(f'D:/PythonApp/{excel_file_name}.xlsx')
            # new_worksheet = new_workbook.add_worksheet()
            # for row in range(len(candidate_info_list_list)):
            #     for col in range(len(candidate_info_list_list[0])):
            #         new_worksheet.write(row, col, candidate_info_list_list[row][col])
            # new_workbook.close()

            # print(candidate_info_list_list)


# main
app = QApplication(sys.argv)
welcome = WelcomeScreen()
widget = QtWidgets.QStackedWidget()
widget.addWidget(welcome)
widget.setFixedHeight(300)
widget.setFixedWidth(800)
widget.show()
try:
    sys.exit(app.exec_())
except:
    pass
