import logging
import pathlib
from typing import Iterable

import numpy as np

from mDeepFRI.database import build_database, search_database
from mDeepFRI.mmseqs import QueryFile
from mDeepFRI.pdb import create_pdb_mmseqs

logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(module)s.%(funcName)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S')

logger = logging.getLogger(__name__)
BAR_FORMAT = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}], {rate_fmt}{postfix}"


def hierarchical_database_search(query_file: str,
                                 output_path: str,
                                 databases: Iterable[str] = [],
                                 min_seq_len: int = None,
                                 max_seq_len: int = None,
                                 min_bits: float = 0,
                                 max_eval: float = 1e-5,
                                 min_ident: float = 0.5,
                                 min_coverage: float = 0.9,
                                 top_k: int = 5,
                                 skip_pdb: bool = False,
                                 overwrite: bool = False,
                                 threads: int = 1):

    output_path = pathlib.Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    # load initial sequences
    query_file = QueryFile(filepath=query_file)
    query_file.load_sequences()
    sequence_num_start = len(query_file.sequences)
    if min_seq_len or max_seq_len:
        query_file.filter_sequences(min_seq_len, max_seq_len)

    dbs = []
    # PDB100 database
    if not skip_pdb:
        logger.info("Creating PDB100 database.")
        pdb100 = create_pdb_mmseqs(threads=threads)
        dbs.append(pdb100)
        logger.info("PDB100 database created.")

    for database in databases:
        database = pathlib.Path(database)
        db = build_database(
            input_path=database,
            output_path=database.parent,
            overwrite=overwrite,
            threads=threads,
        )
        dbs.append(db)

    aligned_total = 0

    for db in dbs:
        best_hits = search_database(query_file=query_file.filepath,
                                    ids=query_file.sequences.keys(),
                                    database=db.mmseqs_db,
                                    min_seq_len=min_seq_len,
                                    max_seq_len=max_seq_len,
                                    min_bits=min_bits,
                                    max_eval=max_eval,
                                    min_ident=min_ident,
                                    min_coverage=min_coverage,
                                    top_k=top_k,
                                    threads=threads)

        best_hits.save(output_path / f"{db.name}_results.tsv")
        # percentage of hits
        unique_hits = np.unique(best_hits["query"])
        aligned_db = len(unique_hits)
        aligned_total += aligned_db
        aligned_perc = round(aligned_db / sequence_num_start * 100, 2)
        total_perc = round(aligned_total / sequence_num_start * 100, 2)
        logger.info(f"Aligned {aligned_db}/{sequence_num_start} "
                    f"({aligned_perc:.2f}%) proteins against {db.name}.")
        logger.info(
            f"Aligned {aligned_total}/{sequence_num_start} ({total_perc:.2f}%) proteins in total."
        )
        query_file.remove_sequences(unique_hits)


# def predict_protein_function(
#         query_file: str,
#         databases: Tuple[str],
#         weights: str,
#         output_path: str,
#         deepfri_processing_modes: List[str] = ["ec", "bp", "mf", "cc"],
#         angstrom_contact_threshold: float = 6,
#         generate_contacts: int = 2,
#         mmseqs_min_bitscore: float = None,
#         mmseqs_max_eval: float = 10e-5,
#         mmseqs_min_identity: float = 0.5,
#         top_k: int = 5,
#         alignment_gap_open: float = 10,
#         alignment_gap_continuation: float = 1,
#         identity_threshold: float = 0.5,
#         remove_intermediate=False,
#         overwrite=False,
#         threads: int = 1,
#         skip_pdb: bool = False,
#         min_length: int = 60,
#         max_length: int = 1000):

#     MIN_SEQ_LEN = min_length
#     MAX_SEQ_LEN = max_length

#     query_file = pathlib.Path(query_file)
#     weights = pathlib.Path(weights)
#     output_path = pathlib.Path(output_path)
#     output_path.mkdir(parents=True, exist_ok=True)

#     deepfri_models_config = load_deepfri_config(weights)

#     # version 1.1 drops support for ec
#     if deepfri_models_config["version"] == "1.1":
#         # remove "ec" from processing modes
#         deepfri_processing_modes = [
#             mode for mode in deepfri_processing_modes if mode != "ec"
#         ]
#         logger.info("EC number prediction is not supported in version 1.1.")

#     assert len(
#         deepfri_processing_modes) > 0, "No valid processing modes selected."

#     deepfri_dbs = []
#     # PDB100 database
#     if not skip_pdb:
#         logger.info(
#             "Creating PDB100 database."
#         )
#         pdb100 = create_pdb_mmseqs()
#         deepfri_dbs.append(pdb100)
#         logger.info("PDB100 database created.")

#     # design solution
#     # database is built in the same directory
#     # where the structure database is stored
#     for database in databases:
#         database = pathlib.Path(database)
#         db = build_database(
#             input_path=database,
#             output_path=database.parent,
#             overwrite=overwrite,
#             threads=threads,
#         )
#         deepfri_dbs.append(db)

#     query_seqs = load_fasta_as_dict(query_file)
#     # sort dictionary by length
#     query_seqs = dict(sorted(query_seqs.items(), key=lambda x: len(x[1])))

#     # filter query seqs and log their sizes
#     to_remove = []
#     for seq in query_seqs:
#         if len(query_seqs[seq]) < MIN_SEQ_LEN:
#             logger.info("Skipping %s; sequence too short %i aa", seq,
#                         len(query_seqs[seq]))
#             to_remove.append(seq)
#         elif len(query_seqs[seq]) > MAX_SEQ_LEN:
#             logger.info("Skipping %s; sequence too long %i aa", seq,
#                         len(query_seqs[seq]))
#             to_remove.append(seq)

#     for seq in to_remove:
#         del query_seqs[seq]

#     aligned_cmaps = []

#     for db in deepfri_dbs:
#         # SEQUENCE ALIGNMENT
#         # calculate already aligned sequences
#         logger.info("Aligning %s sequences against %s.", len(query_seqs),
#                     db.name)

#         # align new sequences agains db
#         alignments = run_alignment(query_file, db.mmseqs_db, db.sequence_db,
#                                    output_path, mmseqs_min_bitscore,
#                                    mmseqs_max_eval, mmseqs_min_identity, top_k,
#                                    alignment_gap_open,
#                                    alignment_gap_continuation, threads)

#         # if anything aligned
#         if not alignments:
#             logger.info("No alignments found for %s.", db.name)
#             continue
#         # filter alignments by identity
#         alignments = [
#             aln for aln in alignments if aln.identity > identity_threshold
#         ]

#         if not alignments:
#             logger.info("All alignments below identity threshold for %s.",
#                         db.name)
#             continue

#         # set a db name for alignments
#         for aln in alignments:
#             aln.db_name = db.name

#         aligned_queries = [aln[0].query_name for aln in aligned_cmaps]
#         new_alignments = {
#             aln.query_name: aln
#             for aln in alignments if aln.query_name not in aligned_queries
#             and aln.query_name in query_seqs
#         }

#         # CONTACT MAP ALIGNMENT
#         # initially designed as a separate step
#         # some protein structures in PDB are not formatted correctly
#         # so contact map alignment fails for them
#         # for this cases we replace closest experimental structure with
#         # closest predicted structure if available
#         # if no alignments were found - report

#         query_ids = [aln.query_name for aln in new_alignments.values()]
#         target_ids = [
#             aln.target_name.rsplit(".", 1)[0]
#             for aln in new_alignments.values()
#         ]

#         # extract structural information
#         # in form of C-alpha coordinates
#         if "pdb100" in db.name:
#             with Pool(threads) as p:
#                 iterable = zip(target_ids, query_ids)
#                 _, coords = zip(*p.starmap(get_pdb_seq_coords, iterable))

#         else:
#             suffix = foldcomp_sniff_suffix(target_ids[0], db.foldcomp_db)
#             if suffix:
#                 target_ids = [f"{t}{suffix}" for t in target_ids]

#             # extracting coordinates from FoldComp
#             with foldcomp.open(db.foldcomp_db, ids=target_ids) as struct_db:
#                 coords = [
#                     extract_residues_coordinates(struct, filetype="pdb")[1]
#                     for _, struct in struct_db
#                 ]

#         for aln, coord in zip(new_alignments.values(), coords):
#             aln.coords = coord

#         partial_align = partial(build_align_contact_map,
#                                 threshold=angstrom_contact_threshold,
#                                 generated_contacts=generate_contacts)

#         with Pool(threads) as p:
#             # align with progress bar
#             partial_cmaps = list(
#                     p.map(partial_align, new_alignments.values())
#                 )

#         # filter errored contact maps
#         # returned as Tuple[AlignmentResult, None] from `retrieve_align_contact_map`
#         partial_cmaps = [cmap for cmap in partial_cmaps if cmap[1] is not None]
#         aligned_cmaps.extend(partial_cmaps)
#         aligned_database = round(len(partial_cmaps) / len(query_seqs) * 100, 2)
#         aligned_total = round(len(aligned_cmaps) / len(query_seqs) * 100, 2)
#         logger.info(
#             f"Aligned {len(partial_cmaps)}/{len(query_seqs)} ({aligned_database}% of total)
# proteins against {db.name}."
#         )
#         logger.info(
#             f"Aligned {len(aligned_cmaps)}/{len(query_seqs)} ({aligned_total}%) proteins in total."
#         )

#     aligned_queries = [aln.query_name for aln in alignments]
#     unaligned_queries = {
#         k: v
#         for k, v in query_seqs.items() if k not in aligned_queries
#     }

#     # deepfri_processing_modes = ['mf', 'bp', 'cc', 'ec']
#     # mf = molecular_function
#     # bp = biological_process
#     # cc = cellular_component
#     # ec = enzyme_commission

#     # sort cmaps by length of query sequence
#     aligned_cmaps = sorted(aligned_cmaps,
#                            key=lambda x: len(x[0].query_sequence))
#     # sort unaligned queries by length
#     unaligned_queries = dict(
#         sorted(unaligned_queries.items(), key=lambda x: len(x[1])))

#     output_file_name = output_path / "results.tsv"
#     output_buffer = open(output_file_name, "w", encoding="utf-8")
#     csv_writer = csv.writer(output_buffer, delimiter="\t")
#     csv_writer.writerow([
#         'Protein',
#         'GO_term/EC_number',
#         'Score',
#         'Annotation',
#         'Neural_net',
#         'DeepFRI_mode',
#         'DB_hit',
#         'DB_name',
#         'Identity',
#     ])

#     # FUNCTION PREDICTION
#     for i, mode in enumerate(deepfri_processing_modes):
#         # GCN
#         gcn_prots = len(aligned_cmaps)
#         if gcn_prots > 0:
#             net_type = "gcn"
#             logger.info("Processing mode: %s; %i/%i", DEEPFRI_MODES[mode],
#                         i + 1, len(deepfri_processing_modes))
#             # GCN for queries with aligned contact map
#             gcn_path = deepfri_models_config[net_type][mode]

#             gcn = Predictor(gcn_path, threads=threads)

#             for i, (aln, aligned_cmap) in tqdm(
#                     enumerate(aligned_cmaps),
#                     total=gcn_prots,
#                     miniters=len(aligned_cmaps) // 10,
#                     desc=f"Predicting with GCN ({DEEPFRI_MODES[mode]})",
#                     bar_format=BAR_FORMAT):

#                 ### PROTEIN LENGTH CHECKS
#                 if len(aln.query_sequence) < MIN_SEQ_LEN:
#                     logger.info("Skipping %s; sequence too short %i aa",
#                                 aln.query_name, len(aln.query_sequence))
#                     continue

#                 elif len(aln.query_sequence) > MAX_SEQ_LEN:
#                     logger.info("Skipping %s; sequence too long - %i aa",
#                                 aln.query_name, len(aln.query_sequence))
#                     continue

#                 logger.debug("Predicting %s; %i/%i", aln.query_name, i + 1,
#                              gcn_prots)
#                 # running the actual prediction
#                 prediction_rows = gcn.predict_function(
#                     seqres=aln.query_sequence,
#                     cmap=aligned_cmap,
#                     chain=str(aln.query_name))
#                 # writing the results to the output file
#                 for row in prediction_rows:
#                     row.extend([net_type, mode])
#                     # corrected name for FoldComp inconsistency
#                     row.extend([
#                         aln.target_name.rsplit(".", 1)[0], aln.db_name,
#                         aln.identity
#                     ])
#                     csv_writer.writerow(row)

#             del gcn

#         # CNN for queries without satisfying alignments
#         cnn_prots = len(unaligned_queries)
#         if cnn_prots > 0:
#             net_type = "cnn"
#             logger.info("Predicting with CNN: %i proteins", cnn_prots)
#             cnn_path = deepfri_models_config[net_type][mode]
#             cnn = Predictor(cnn_path, threads=threads)
#             for i, query_id in tqdm(
#                     enumerate(unaligned_queries),
#                     total=cnn_prots,
#                     miniters=len(unaligned_queries) // 10,
#                     desc=f"Predicting with CNN ({DEEPFRI_MODES[mode]})",
#                     bar_format=BAR_FORMAT):

#                 seq = query_seqs[query_id]
#                 if len(seq) > MAX_SEQ_LEN:
#                     logger.info("Skipping %s; sequence too long %i aa.",
#                                 query_id, len(seq))
#                     continue

#                 elif len(seq) < MIN_SEQ_LEN:
#                     logger.info("Skipping %s; sequence too short %i aa.",
#                                 query_id, len(seq))
#                     continue

#                 logger.debug("Predicting %s; %i/%i", query_id, i + 1,
#                              cnn_prots)
#                 prediction_rows = cnn.predict_function(
#                     seqres=query_seqs[query_id], chain=str(query_id))
#                 for row in prediction_rows:
#                     row.extend([net_type, mode])
#                     row.extend([np.nan, np.nan, np.nan])
#                     csv_writer.writerow(row)

#             del cnn

#     output_buffer.close()

#     if remove_intermediate:
#         for db in deepfri_dbs:
#             remove_intermediate_files([db.sequence_db, db.mmseqs_db])

#     logger.info("meta-DeepFRI finished successfully.")
