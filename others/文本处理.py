with open('ts.txt', 'r+', encoding='utf-8') as fp:
    a=fp.readlines()
    with open('ts2.txt', 'w+', encoding='utf-8') as fp1:
        for i in a:
            if 'witter' not in i and '早' not in i and 'http' not in i  and 'gn' not in i and '午' not in i and '晚' not in i and '|' not in i:
                fp1.write(i.split('次')[-1])
