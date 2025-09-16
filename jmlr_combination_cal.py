import pandas as pd
import os


def jmlr_combination(start_year=2020, end_year=2025):
    dfs = []
    if not os.path.exists('jmlr_combination.csv'):
        for year in range(start_year, end_year):
            dfs.append(pd.read_csv(f'jmlr_{year}_key_metadata.csv'))
        dfs = pd.concat(dfs)
        dfs.to_csv('jmlr_combination.csv', index=False)
    else:
        dfs = pd.read_csv('jmlr_combination.csv')


def count_jmlr_pdf(start_year=2020, end_year=2025):
    def count_pdf_files(directory):
        count = 0
        for filename in os.listdir(directory):
            if filename.lower().endswith('.pdf'):
                count += 1
        return count

    main_track_count = []
    software_track_count = []
    for year in range(start_year, end_year):
        main_track_directory = f'JMLR {year}' + '/main_track'
        software_track_directory = f'JMLR {year}' + '/software_track'
        for directory in [main_track_directory, software_track_directory]:
            if os.path.exists(directory):
                count = count_pdf_files(directory)
                if directory == main_track_directory:
                    print(f'Year {year}: {count} PDF files {main_track_directory}')
                    main_track_count.append(count)
                else:
                    print(f'Year {year}: {count} PDF files {software_track_directory}')
                    software_track_count.append(count)
            else:
                print(f'Year {year} {directory}: Directory does not exist')
    return main_track_count, software_track_count , sum(main_track_count), sum(software_track_count)

def standardlize_affi_area(path):
    df = pd.read_csv(path)
    areas = df['area'].tolist()
    affis = df['seperated'].tolist()

    def standardize_area(areas):
        error_area = []
        for i,area in enumerate(areas):
            if ',' in area or ':' not in area:
                error_area.append(area)
                print(f'Error area at index {i}: {area}')
            area = area.split(':')[-1].strip()
            area = area.split(' ')[-1].strip()
            if area == 'Unknown':
                error_area.append(area)
                print(f'Error area at index {i}: {area}')
            areas[i] = area
        return areas, error_area
    
    def standardize_affiliation(affiliations):
        error_affi = []
        for i,affi in enumerate(affiliations):
            if ',' in affi or ':' not in affi:
                error_affi.append(affi)
                print(f'Error affiliation at index {i}: {affi}')
            affi = affi.split(':')[-1].strip()
            affiliations[i] = affi
            
        return affiliations, error_affi
            
    areas, error_area = standardize_area(areas)
    affis, error_affi = standardize_affiliation(affis)
    df['area'] = areas
    df['seperated'] = affis
    df.to_csv('cal'+path, index=False)
    return areas, affis, error_area, error_affi 

from collections import defaultdict
def cal_standardlized_csv(path):
    df = pd.read_csv(path)
    area_count = defaultdict(int)
    affi_count = defaultdict(int)
    affi_and_area = dict()
    for area in df['area'].tolist():
        area_count[area] += 1
    for i,affi in enumerate(df['seperated'].tolist()):
        affi_count[affi] += 1
        if affi not in affi_and_area:
            affi_and_area[affi] = df['area'].tolist()[i] 
        elif affi_and_area[affi] != df['area'].tolist()[i]:
            affi_and_area[affi] += ',' + df['area'].tolist()[i]
    sorted_area_count = sorted(list(area_count.items()), key=lambda x: x[1], reverse=True)
    sorted_affi_count = sorted(list(affi_count.items()), key=lambda x: x[1], reverse=True)
    print('Nanjing University affiliation count:', affi_count['Nanjing University'])
    print('Top 20 areas:')
    for area, count in sorted_area_count[:20]:
        print(f'{area}: {count}')
    print('Top 50 affiliations:')
    for affi, count in sorted_affi_count[:50]:
        print(f'{affi}: {count} area: {affi_and_area[affi]}')
    for i, (affi, count) in enumerate(sorted_affi_count):
        sorted_affi_count[i] = (affi, count, affi_and_area[affi])
    pd.DataFrame(sorted_area_count, columns=['area', 'count']).to_csv('area_count.csv', index=False)
    pd.DataFrame(sorted_affi_count, columns=['affiliation', 'count','area']).to_csv('affiliation_count.csv', index=False)

if __name__ == "__main__":

    jmlr_combination()
    main_track_count, software_track_count, main_sum, software_sum = count_jmlr_pdf()
    print(f'Main track counts per year: {main_track_count}, Total: {main_sum}')
    print(f'Software track counts per year: {software_track_count}, Total: {software_sum}')

    areas, affis, error_area, error_affi = standardlize_affi_area('jmlr_combination.csv')
    print(f'areas: {areas[:40]}')
    print(f'affis: {affis[:40]}')
    print(f'Error areas: {error_area}')
    print(f'Error affiliations: {error_affi}')
    

    cal_standardlized_csv('caljmlr_combination.csv')