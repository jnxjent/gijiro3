from table_writer import table_writer as write_table_data

from minutes_writer import write_minutes_section

def write_information_to_existing_table(word_file_path: str, output_file_path: str, full_transcription, extracted_info):
    """
    互換性のための関数名 (旧API互換)
    """
    process_document(word_file_path, output_file_path, full_transcription, extracted_info)

def process_document(word_file_path: str, output_file_path: str, full_transcription, extracted_info):
    """
    統合関数: テーブルと議事録の両方を処理
    """
    write_table_data(word_file_path, output_file_path, full_transcription, extracted_info)
    write_minutes_section(word_file_path,output_file_path, full_transcription, extracted_info)
