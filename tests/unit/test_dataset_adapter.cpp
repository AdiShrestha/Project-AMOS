#include "../../source/include/klstream/feature/behavior_source.hpp"
#include <cassert>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <string>
#include <utility>

using namespace klstream;

static void create_temp_file(const std::string& path, const std::string& content) {
    std::ofstream f(path);
    f << content;
    f.close();
}

int main() {
    std::cout << "[test_dataset_adapter] Starting adapter verification..." << std::endl;

    // 1. Valid Taobao CSV (9 columns)
    {
        std::string taobao_csv = "/tmp/test_adapter_taobao_valid.csv";
        create_temp_file(taobao_csv,
            "seq,timestamp_ns,user_id,item_id,category_id,behavior_code,label,label_valid,is_burst_period\n"
            "0,1511568000000000000,101,2001,301,0,0,0,0\n"
            "1,1511568001000000000,101,2002,301,1,0,0,0\n"
            "2,1511568002000000000,101,2003,302,2,0,0,0\n"
            "3,1511568003000000000,101,2004,302,3,1,1,0\n"
        );
        auto rows = load_replay_csv(taobao_csv, DatasetMode::Taobao);
        assert(rows.size() == 4);
        assert(rows[0].seq == 0 && rows[0].behavior_code == 0 && rows[0].amount == 0.0f);
        assert(rows[3].seq == 3 && rows[3].behavior_code == 3 && rows[3].label == 1 && rows[3].label_valid == 1);
        std::cout << "  - Valid Taobao load: PASS" << std::endl;
        std::remove(taobao_csv.c_str());
    }

    // 2. Valid ULB CSV (10 columns, with amount)
    {
        std::string ulb_csv = "/tmp/test_adapter_ulb_valid.csv";
        create_temp_file(ulb_csv,
            "seq,timestamp_ns,user_id,item_id,category_id,behavior_code,amount,label,label_valid,is_burst_period\n"
            "0,1511568000000000000,0,0,0,0,149.50,0,1,0\n"
            "1,1511568001000000000,0,0,0,0,2.69,1,1,0\n"
        );
        auto rows = load_replay_csv(ulb_csv, DatasetMode::ULB);
        assert(rows.size() == 2);
        assert(rows[0].seq == 0 && rows[0].amount == 149.50f && rows[0].behavior_code == 0);
        assert(rows[1].seq == 1 && rows[1].amount == 2.69f && rows[1].label == 1);
        std::cout << "  - Valid ULB load: PASS" << std::endl;
        std::remove(ulb_csv.c_str());
    }

    // 2b. Label lookup follows source sequence identity, even when sparse.
    {
        std::vector<BehaviorRow> sparse_rows{
            BehaviorRow{10, 1511568000000000000ULL, 101, 2001, 301, 0, 0.0f, 0, 0, 0},
            BehaviorRow{20, 1511568001000000000ULL, 101, 2002, 301, 3, 0.0f, 1, 1, 0},
        };
        BehaviorSource source(std::move(sparse_rows), ReplayMode::MaxRate);
        const auto first_label = source.label_for_seq(10);
        const auto second_label = source.label_for_seq(20);
        assert(first_label.first == 0 && first_label.second == 0);
        assert(second_label.first == 1 && second_label.second == 1);
        std::cout << "  - Sparse sequence label identity: PASS" << std::endl;
    }

    // 3. Fail-closed: Taobao CSV missing columns (only 8 columns)
    {
        std::string taobao_bad = "/tmp/test_adapter_taobao_bad_cols.csv";
        create_temp_file(taobao_bad,
            "seq,timestamp_ns,user_id,item_id,category_id,behavior_code,label,label_valid\n"
            "0,1511568000000000000,101,2001,301,0,0,0\n"
        );
        bool caught = false;
        try {
            load_replay_csv(taobao_bad, DatasetMode::Taobao);
        } catch (const std::runtime_error& e) {
            caught = true;
        }
        assert(caught);
        std::cout << "  - Fail-closed missing Taobao columns: PASS" << std::endl;
        std::remove(taobao_bad.c_str());
    }

    // 4. Fail-closed: Unknown behavior code in Taobao (e.g. 5)
    {
        std::string taobao_unknown_code = "/tmp/test_adapter_taobao_unknown_code.csv";
        create_temp_file(taobao_unknown_code,
            "seq,timestamp_ns,user_id,item_id,category_id,behavior_code,label,label_valid,is_burst_period\n"
            "0,1511568000000000000,101,2001,301,5,0,0,0\n"
        );
        bool caught = false;
        try {
            load_replay_csv(taobao_unknown_code, DatasetMode::Taobao);
        } catch (const std::runtime_error& e) {
            caught = true;
        }
        assert(caught);
        std::cout << "  - Fail-closed unknown Taobao behavior code: PASS" << std::endl;
        std::remove(taobao_unknown_code.c_str());
    }

    // 5. Fail-closed: ULB given non-zero behavior code
    {
        std::string ulb_bad_code = "/tmp/test_adapter_ulb_bad_code.csv";
        create_temp_file(ulb_bad_code,
            "seq,timestamp_ns,user_id,item_id,category_id,behavior_code,amount,label,label_valid,is_burst_period\n"
            "0,1511568000000000000,0,0,0,1,10.0,0,1,0\n"
        );
        bool caught = false;
        try {
            load_replay_csv(ulb_bad_code, DatasetMode::ULB);
        } catch (const std::runtime_error& e) {
            caught = true;
        }
        assert(caught);
        std::cout << "  - Fail-closed non-zero ULB behavior code: PASS" << std::endl;
        std::remove(ulb_bad_code.c_str());
    }

    // 6. Fail-closed: File not found
    {
        bool caught = false;
        try {
            load_replay_csv("/tmp/non_existent_path_xyz_123.csv", DatasetMode::Taobao);
        } catch (const std::runtime_error& e) {
            caught = true;
        }
        assert(caught);
        std::cout << "  - Fail-closed non-existent file: PASS" << std::endl;
    }

    // 7. Fail-closed: positional data with an unrecognized header
    {
        std::string bad_header = "/tmp/test_adapter_bad_header.csv";
        create_temp_file(bad_header,
            "anything,anything_else,still_not_schema\n"
            "0,1511568000000000000,101\n");
        bool caught = false;
        try {
            load_replay_csv(bad_header, DatasetMode::Taobao);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        assert(caught);
        std::cout << "  - Fail-closed unknown replay header: PASS" << std::endl;
        std::remove(bad_header.c_str());
    }

    // 8. Fail-closed: duplicate/non-increasing source sequence
    {
        std::string duplicate_seq = "/tmp/test_adapter_duplicate_seq.csv";
        create_temp_file(duplicate_seq,
            "seq,timestamp_ns,user_id,item_id,category_id,behavior_code,label,label_valid,is_burst_period\n"
            "0,1511568000000000000,101,2001,301,0,0,0,0\n"
            "0,1511568001000000000,101,2002,301,1,0,0,0\n");
        bool caught = false;
        try {
            load_replay_csv(duplicate_seq, DatasetMode::Taobao);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        assert(caught);
        std::cout << "  - Fail-closed duplicate sequence: PASS" << std::endl;
        std::remove(duplicate_seq.c_str());
    }

    // 9. Fail-closed: ULB must not acquire a fabricated entity identity
    {
        std::string ulb_identity = "/tmp/test_adapter_ulb_identity.csv";
        create_temp_file(ulb_identity,
            "seq,timestamp_ns,user_id,item_id,category_id,behavior_code,amount,label,label_valid,is_burst_period\n"
            "0,1511568000000000000,42,0,0,0,10.0,0,1,0\n");
        bool caught = false;
        try {
            load_replay_csv(ulb_identity, DatasetMode::ULB);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        assert(caught);
        std::cout << "  - Fail-closed fabricated ULB identity: PASS" << std::endl;
        std::remove(ulb_identity.c_str());
    }

    // 10. Equal timestamps preserve seq order; backward keyed time fails.
    {
        std::string ties = "/tmp/test_adapter_ties.csv";
        create_temp_file(ties,
            "seq,timestamp_ns,user_id,item_id,category_id,behavior_code,label,label_valid,is_burst_period\n"
            "0,1511568000000000000,101,2001,301,0,0,0,0\n"
            "1,1511568000000000000,101,2002,301,1,0,0,0\n");
        auto rows = load_replay_csv(ties, DatasetMode::Taobao);
        assert(rows.size() == 2 && rows[0].seq < rows[1].seq);
        std::remove(ties.c_str());

        std::string backwards = "/tmp/test_adapter_backwards.csv";
        create_temp_file(backwards,
            "seq,timestamp_ns,user_id,item_id,category_id,behavior_code,label,label_valid,is_burst_period\n"
            "0,1511568001000000000,101,2001,301,0,0,0,0\n"
            "1,1511568000000000000,101,2002,301,1,0,0,0\n");
        bool caught = false;
        try {
            load_replay_csv(backwards, DatasetMode::Taobao);
        } catch (const std::runtime_error&) {
            caught = true;
        }
        assert(caught);
        std::cout << "  - Tie order and backward-time guard: PASS" << std::endl;
        std::remove(backwards.c_str());
    }

    std::cout << "[test_dataset_adapter] All adapter tests PASSED successfully." << std::endl;
    return 0;
}
