
# download jmlr main track and software track papers separately

from urllib.request import urlopen
from bs4 import BeautifulSoup
import os
import urllib.request
import sys
import re


def Schedule(a, b, c):
    # a:已经下载的数据块
    # b:数据块的大小
    # c:远程文件的大小
    per = 100.0 * a * b / c
    if per > 100:
        per = 100
    sys.stdout.write('\rDownloading: ' + '%.2f%%' % per)

###根据url链接提取下载文件的大小特征
def getRemoteFileSize(url):
    '''
    通过content-length头获取远程文件大小
    '''
    opener = urllib.request.build_opener()
    try:
        request = urllib.request.Request(url)
        request.get_method = lambda: 'HEAD'
        response = opener.open(request)
        response.read()
    except:
        # 远程文件不存在
        return 0
    else:
        getfileSize = dict(response.headers).get('Content-Length', 0)
        filesize = round(float(getfileSize) / 1048576, 2)
        return filesize

def download_file(file_url, file_path):
    if os.path.exists(file_path):
        return True
    tmp_file_path = file_path + '.tmp'

    filesize = getRemoteFileSize(file_url)
    print("File size:", filesize, 'MB')
    if filesize > 100:
        print("File size more than 100 MB, skip!")
        return 2

    if filesize == 0:
        print("File size is 0 MB, skip!")
        return 0

    try:
        urllib.request.urlretrieve(file_url, tmp_file_path, Schedule)
        urllib.request.urlcleanup()
        os.rename(tmp_file_path, file_path)
    except (urllib.error.ContentTooShortError, urllib.error.HTTPError):
        print('\nredownloading...')
        download_file(file_url, file_path)

    while True:
        if os.path.exists(file_path):
            break

    sys.stdout.write('\rDownload over\n')

    return 1

def formalize_file_name(paper_title):
    title=paper_title
    for sign in '\/:*<>|?.,"$':
        title = title.replace(sign, ' ')
    return title.strip()

if __name__=='__main__':
    all_papers_url='https://jmlr.org/papers/v21/'  # todo: modify the url
    pdf_pre_url='https://jmlr.org'

    url_content = urlopen(all_papers_url).read()
    url_content=url_content.replace(b'</b></i>',b'</i></b>')
    soup = BeautifulSoup(url_content, 'html.parser')
    paper_list = soup.find_all('dl')
    print('There are %d papers to download.'%(len(paper_list)))

    paper_download_failed_list = []

    # for paper_info in paper_list:
    #     title=paper_info.find('dt').text.split('\n')[0]
    #     link_info=paper_info.find_all('a',attrs={'target':'_blank'})
    #     paper_link=''
    #     for link in link_info:
    #         if link.get('href').endswith('.pdf'):
    #             paper_link=link.get('href')
    #     if paper_link.startswith('http'):
    #         download_link=paper_link
    #     else:
    #         download_link=pdf_pre_url+paper_link
    #     year_info=paper_info.find('dd').text
    #     year=re.findall(r"\d\d\d\d.",year_info)[0].strip()[:-1]
    #     print(title,download_link,year)

    for index,paper_info in enumerate(paper_list):
        title=paper_info.find('dt').text.split('\n')[0]
        title=formalize_file_name(title)
        print('Index: %d\tPaper title: %s' % (index + 1, title))

        year_info = paper_info.find('dd').text
        year = re.findall(r" \d\d\d\d.", year_info)[0].strip()[:-1]
        if not year.isdigit():
            paper_download_failed_list.append(title)
            print(title + ': invalid year!')
            continue

        target_folder='./JMLR '+year
        if not os.path.exists(target_folder):
            os.mkdir(target_folder)
        
        main_track_folder=os.path.join(target_folder,'main_track')
        soft_track_folder=os.path.join(target_folder,'software_track')
        if not os.path.exists(main_track_folder):
            os.mkdir(main_track_folder)
        if not os.path.exists(soft_track_folder):
            os.mkdir(soft_track_folder)

        main_pdf_path=os.path.join(main_track_folder,title+'.pdf')
        soft_pdf_path=os.path.join(soft_track_folder,title+'.pdf')

        if not os.path.exists(main_pdf_path) and not os.path.exists(soft_pdf_path):
            is_mloss = paper_info.find('a', href="http://www.jmlr.org/mloss/") is not None
            link_info = paper_info.find_all('a', attrs={'target': '_blank'})
            paper_link = ''
            for link in link_info:
                if link.get('href').endswith('.pdf'):
                    paper_link = link.get('href')
            if paper_link.startswith('http'):
                download_link = paper_link
            else:
                download_link = pdf_pre_url + paper_link
            if is_mloss:
                pdf_path = soft_pdf_path
                print('This paper is from software track.')
            else:
                pdf_path = main_pdf_path
                print('This paper is from main track.')
            state = download_file(download_link, pdf_path)
            if state == 0:
                print(title + ': the main file occurs 404 error!')
                paper_download_failed_list.append(title)
        else:
            print('file already exists!')
    print('The following papers failed to download!')
    print(paper_download_failed_list)