import time

import tempfile
import os
import pytest

from functools import partial
from Bio import pairwise2

default_pair_align = partial(
    pairwise2.align.globalms, match=2, mismatch=-1, open=-0.5, extend=-0.1, one_alignment_only=True)

from meta_deepFRI.utils import (bio_utils, fasta_file_io, search_alignments, utils)
# hash_sequence_id, encode_faa_ids, load_fasta_file, write_fasta_file


def test_protein_letters():

    expected = {
        'ALA': 'A',
        'CYS': 'C',
        'ASP': 'D',
        'GLU': 'E',
        'PHE': 'F',
        'GLY': 'G',
        'HIS': 'H',
        'ILE': 'I',
        'LYS': 'K',
        'LEU': 'L',
        'MET': 'M',
        'ASN': 'N',
        'PRO': 'P',
        'GLN': 'Q',
        'ARG': 'R',
        'SER': 'S',
        'THR': 'T',
        'VAL': 'V',
        'TRP': 'W',
        'TYR': 'Y',
        'ASX': 'B',
        'XAA': 'X',
        'GLX': 'Z',
        'XLE': 'J',
        'SEC': 'U',
        'PYL': 'O',
        'UNK': 'X'
    }
    assert bio_utils.PROTEIN_LETTERS == expected


@pytest.fixture
def fasta_path(tmpdir_factory):
    """Create a temporary FASTA file and return its path."""
    # Create a temporary directory
    temp_dir = tmpdir_factory.mktemp("fasta_files")
    # Create a temporary FASTA file
    fasta_file = temp_dir.join("test.fasta")
    fasta_file.write(">seq1\nATGC\n>seq2\nCGTA")
    return str(fasta_file)


def test_load_fasta_file(fasta_path):
    # Load the FASTA file
    seq_records = fasta_file_io.load_fasta_file(fasta_path)

    # Check that the correct number of records was loaded
    assert len(seq_records) == 2

    # Check that the IDs and sequences were loaded correctly
    assert seq_records[0].id == "seq1"
    assert seq_records[0].seq == "ATGC"
    assert seq_records[1].id == "seq2"
    assert seq_records[1].seq == "CGTA"


def test_write_fasta_file(fasta_path):
    # Create some SeqRecord objects
    seq_records = [
        fasta_file_io.SeqRecord(id="seq1", seq="ATGC"),
        fasta_file_io.SeqRecord(id="seq2", seq="CGTA"),
    ]

    # Write the SeqRecord objects to a FASTA file
    output_path = os.path.join(os.path.dirname(fasta_path), "output.fasta")
    fasta_file_io.write_fasta_file(seq_records, output_path)

    # Load the written FASTA file
    written_seq_records = fasta_file_io.load_fasta_file(output_path)

    # Check that the correct number of records was written
    assert len(written_seq_records) == 2

    # Check that the IDs and sequences were written correctly
    assert written_seq_records[0].id == "seq1"
    assert written_seq_records[0].seq == "ATGC"
    assert written_seq_records[1].id == "seq2"
    assert written_seq_records[1].seq == "CGTA"


def test_load_fasta_file_raises_error_for_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        fasta_file_io.load_fasta_file("nonexistent.fasta")


def test_write_fasta_file_raises_error_for_invalid_output_path():
    with tempfile.TemporaryDirectory() as temp_dir:
        seq_records = [
            fasta_file_io.SeqRecord(id="seq1", seq="ATGC"),
            fasta_file_io.SeqRecord(id="seq2", seq="CGTA"),
        ]
        with pytest.raises(IsADirectoryError):
            fasta_file_io.write_fasta_file(seq_records, temp_dir)


def test_hash_sequence_id():
    # Test hash function with a known input and output
    assert fasta_file_io.hash_sequence_id("test") == "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"


def test_encode_faa_ids(fasta_path):
    # Run the encode_faa_ids function on the test FASTA file
    faa_hashed_ids_path, hash_lookup_dict = fasta_file_io.encode_faa_ids(fasta_path)

    # Check that the output files were created
    assert os.path.exists(faa_hashed_ids_path)

    # Check that the hash lookup dictionary was created correctly
    assert len(hash_lookup_dict) == 2
    assert "seq1" in hash_lookup_dict.values()
    assert "seq2" in hash_lookup_dict.values()

    # Load the hashed ID FASTA file
    seq_records = fasta_file_io.load_fasta_file(faa_hashed_ids_path)

    # Check that the sequence IDs were encoded correctly
    assert seq_records[0].id != "seq1"
    assert seq_records[1].id != "seq2"

    # Check that the hash lookup dictionary can be used to get the original IDs
    assert hash_lookup_dict[seq_records[0].id] == "seq1"
    assert hash_lookup_dict[seq_records[1].id] == "seq2"


def test_encode_faa_ids_raises_error_for_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        fasta_file_io.encode_faa_ids("nonexistent.fasta")


@pytest.mark.parametrize("alignment, expected_output", [
    (default_pair_align('ATCG', 'ATCG')[0], 1.0),
    (default_pair_align('ATCG', 'AGCG')[0], 0.6),
    (default_pair_align('ATCG', 'CGTA')[0], 0.3),
    (default_pair_align('ATCG', 'ATCGG')[0], 0.8),
])
def test_alignment_sequences_identity(alignment, expected_output):
    # Call the function with the test input
    result = round(search_alignments.alignment_sequences_identity(alignment), 1)

    # Check whether the result matches the expected output
    assert result == expected_output


def test_load_deepfri_config(tmp_path):
    """Test load_deepfri_config() function."""
    tmp_json_file = tmp_path / "model_config.json"
    tmp_json_file.write_text('{"model1": "./trained_models/model1.h5", "model2": "./trained_models/model2.h5"}')

    config = utils.load_deepfri_config(str(tmp_json_file))

    assert config["model1"] == str(tmp_path / "model1.h5")
    assert config["model2"] == str(tmp_path / "model2.h5")


def test_load_deepfri_config_file_not_found():
    """Test FileNotFoundError is raised if config file is not found."""
    with pytest.raises(FileNotFoundError):
        utils.load_deepfri_config("non_existing_file.json")
