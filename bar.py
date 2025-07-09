#https://alexwlchan.net/2018/ascii-bar-charts/
# ▓ █

def draw(data):
    chart = ""

    unit = '▓'
    max_value = max(count for _, count in data)
    increment = max_value / 25
    if increment < 1:
        increment = 1

    longest_label_length = max(len(label) for label, _ in data)

    for label, count in data:

        bar_chunks, remainder = 0, 0
        if increment:
            bar_chunks, remainder = divmod(int(count * 8 / increment), 8)

        bar = unit * bar_chunks

        #if remainder > 0:
        #    bar += chr(ord(unit) + (8 - remainder))

        bar = bar or  '▏'

        chart += f'{label.ljust(longest_label_length)} ▏ {count:#4d} {bar}\n'

    return chart[:-1]
