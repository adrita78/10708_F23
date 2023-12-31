import os
import csv

def label_sequences(fasta_content, label):
    labeled_sequences = []
    records = fasta_content.split('>')[1:]
    for record in records:
        header, sequence = record.split('\n', 1)
        header = header.strip()
        sequence = sequence.replace('\n', '').strip()
        labeled_sequences.append((sequence, label))

    return labeled_sequences

def process_file(file_path, label):
    with open(file_path, 'r') as file:
        fasta_content = file.read()

    return label_sequences(fasta_content, label)

def process_folder(folder_path, label):
    labeled_sequences = []
    files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]


    for file_name in files:
        file_path = os.path.join(folder_path, file_name)
        labeled_sequences.extend(process_file(file_path, label))

    return labeled_sequences

positive_folder_path = "/content/drive/MyDrive/PGM_Project/dockground/dockground/fasta"
positive_labeled_sequences = process_folder(positive_folder_path, label=1)


negative_folder_path = "/content/drive/MyDrive/PGM_Project/marks/fasta"
negative_labeled_sequences = process_folder(negative_folder_path, label=0)


combined_labeled_sequences = positive_labeled_sequences + negative_labeled_sequences


output_folder = "/content/drive/MyDrive/PGM_Project/fasta_files"
output_file_path = os.path.join(output_folder, "combined_labeled_sequences.csv")

with open(output_file_path, 'w', newline='') as output_file:
    csv_writer = csv.writer(output_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)


    csv_writer.writerow(['Sequence', 'Label'])

    for sequence, label in combined_labeled_sequences:
        csv_writer.writerow([sequence, label])
