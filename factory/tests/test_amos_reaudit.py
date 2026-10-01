"""FABRICATION-DISCLOSURE: counterexamples and mutations; no research data."""
import contextlib
import hashlib
from fractions import Fraction
import io
import itertools
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import gatekeeper as g
from engine.metrics import EvidenceError, paired_inference, quantile, number, binary_metrics
from engine.schema import ValidationError, expect_float, validate_training_manifest, validate_split_manifest
from engine.io import read_json, write_json, merkle_root
from engine.audit import Audit
from engine.supervisor import _pub_key_path
from verify_bundle_standalone import verify_bundle
from test_v3 import fixture, evaluate


class ArithmeticCounterexamples(unittest.TestCase):
    def test_snapshot_rejects_short_hash_ambiguity(self):
        for values in ({'ab':'cd'}, {'a':'62cd'}):
            with self.assertRaises(EvidenceError):merkle_root(values)

    def test_merkle_tree_matches_independent_small_reference(self):
        leaves=[]
        files={'a':hashlib.sha256(b'A').hexdigest(),'bb':hashlib.sha256(b'B').hexdigest(),'ccc':hashlib.sha256(b'C').hexdigest()}
        for name, value in files.items():
            leaves.append(hashlib.sha256(b'factory.snapshot.leaf.v1\0'+len(name).to_bytes(8,'big')+name.encode()+bytes.fromhex(value)).digest())
        left=hashlib.sha256(b'factory.snapshot.node.v1\0'+leaves[0]+leaves[1]).digest()
        tree=hashlib.sha256(b'factory.snapshot.node.v1\0'+left+leaves[2]).digest()
        expected=hashlib.sha256(b'factory.snapshot.root.v1\0'+(3).to_bytes(8,'big')+tree).hexdigest()
        self.assertEqual(merkle_root(files),expected)
    def test_sign_flip_is_invariant_to_tiny_and_large_unit_rescaling(self):
        for scale in (1.0, 1e-16, 1e100, 1e-300):
            self.assertEqual(paired_inference([scale]*5, [0]*5, draws=1000)["p_raw"], Fraction(1,16))

    def test_sign_flip_matches_independent_fraction_enumeration(self):
        for values in ([1.0, -2.0, 4.0], [0.1, -0.3, 0.2, 0.6], [1e-17, 2e-17, -1e-17]):
            d = [Fraction.from_float(x) for x in values]
            observed = abs(sum(d))
            reference = sum(abs(sum(x*s for x,s in zip(d,signs))) >= observed
                            for signs in itertools.product((-1,1), repeat=len(d))) / 2**len(d)
            self.assertEqual(paired_inference(values, [0]*len(d), draws=1000)["p_raw"], reference)

    def test_extreme_finite_quantile_midpoint_does_not_overflow(self):
        self.assertEqual(quantile([-1e308, 1e308], .5), 0)
        self.assertAlmostEqual(quantile([-1e308, 1e308], .75)/1e308, .5)

    def test_quantile_rejects_boolean_and_nonfinite_probability(self):
        for q in (True, float("nan"), float("inf")):
            with self.assertRaises(EvidenceError): quantile([1,2], q)

    def test_overflowing_input_and_pair_difference_fail(self):
        with self.assertRaises(EvidenceError): number(10**1000)
        with self.assertRaises(EvidenceError): paired_inference([1e308]*2, [-1e308]*2, draws=1000)
        with self.assertRaises(ValidationError): expect_float(10**1000)

    def test_inference_settings_are_typed_and_finite(self):
        for settings in ({"draws":1000.0},{"draws":True},{"alpha":True},{"seed":True},{"seed":-1}):
            with self.assertRaises(EvidenceError): paired_inference([1,2],[0,0],**settings)

    def test_pairwise_auroc_and_threshold_group_ap_reference(self):
        labels=[0,1,0,1]
        for scores in itertools.product((0.0,.5,1.0),repeat=4):
            pairs=[(scores[i],scores[j]) for i in range(4) for j in range(4) if labels[i]==1 and labels[j]==0]
            auc=sum((a>b)+.5*(a==b) for a,b in pairs)/len(pairs)
            ap=0
            for threshold in sorted(set(scores),reverse=True):
                selected=[i for i,s in enumerate(scores) if s>=threshold]
                newly_positive=sum(labels[i] for i,s in enumerate(scores) if s==threshold)
                ap+=(newly_positive/2)*(sum(labels[i] for i in selected)/len(selected))
            metrics=binary_metrics(labels,scores)
            self.assertEqual(metrics['auroc'],auc)
            self.assertAlmostEqual(metrics['average_precision'],ap)

    def test_fractional_epochs_and_counts_are_rejected(self):
        with self.assertRaises(ValidationError): validate_training_manifest({"epochs_trained":10.5})
        with self.assertRaises(ValidationError): validate_split_manifest({"test_label_distribution":{"0":30.5,"1":20}})


class HonestDiagnostics(unittest.TestCase):
    def test_f1_precision_recall_accuracy_have_no_universal_half_chance(self):
        for metric in ('f1','precision','recall','accuracy','balanced_accuracy'):
            self.assertEqual(g._result_findings({'metric':metric,'value':.2,'verdict':'SUPPORTED'}),[])

    def test_negative_verdicts_do_not_match_all_supported(self):
        self.assertEqual(g._result_findings({'entries':[{'verdict':'NOT_SUPPORTED'}]*3}),[])

    def test_narrow_nonzero_interval_has_no_absolute_unit_floor(self):
        self.assertEqual(g._result_findings({'ci':[1e-18,2e-18],'n':100}),[])

    def test_unresolved_and_malformed_investigations_block(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(g.verify_result_plausibility({'p':0,'investigation_note':'pending','investigation_disposition':'unresolved'}),g.EXIT_PLAUSIBILITY)
            self.assertEqual(g.verify_result_plausibility({'p':2,'investigation_note':'present'}),g.EXIT_PLAUSIBILITY)
            self.assertEqual(g.verify_result_plausibility({'ci':[2,1]}),g.EXIT_PLAUSIBILITY)


class AuditPathMutations(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        fixture(self.root)
        self.environment=patch.dict(os.environ,{'FACTORY_SUPERVISOR_KEY':str(self.root/'keys/local.key')})
        self.environment.start();self.addCleanup(self.environment.stop)
        self.redirect=contextlib.redirect_stdout(io.StringIO())
        self.redirect.__enter__();self.addCleanup(self.redirect.__exit__,None,None,None)
        g.freeze(self.root)
        self.assertEqual(g.run_exp(self.root,'known'),0)
        _,epoch,_=g.active(self.root)
        self.execution=epoch/'runs/known/attempt0001/execution.json'

    def test_local_runner_reports_unknown_cpu_and_memory(self):
        resources=read_json(self.execution)['supervisor_receipt']['resource_observations']
        self.assertEqual(resources,{'cpu_time_seconds':None,'memory_peak_bytes':None})
        self.assertEqual(evaluate(self.root)['errors'],[])

    def test_corrupt_signature_fails_actual_audit(self):
        value=read_json(self.execution)
        value['supervisor_receipt']['supervisor_signature']='not-a-signature'
        write_json(self.execution,value)
        self.assertTrue(evaluate(self.root)['errors'])

    def test_snapshot_root_is_recomputed_on_actual_frozen_path(self):
        plan,epoch,freeze=g.plan_at(self.root),g.active(self.root)[1],g.active(self.root)[2]
        freeze['snapshot_merkle_root']='0'*64
        with self.assertRaisesRegex(EvidenceError,'snapshot root'):
            Audit(self.root,plan,epoch,freeze,g.engine_hash()).frozen()

    def test_failed_attempt_signature_is_checked_after_successful_retry(self):
        root=self.root/'retry';root.mkdir();fixture(root)
        source=root/'source/run.py'
        source.write_text("import sys\nfrom pathlib import Path\nif Path(sys.argv[1]).name=='attempt0001': sys.exit(9)\n"+source.read_text())
        g.freeze(root)
        self.assertEqual(g.run_exp(root,'known'),g.EXIT_EVIDENCE)
        self.assertEqual(g.run_exp(root,'known'),0)
        self.assertEqual(evaluate(root)['errors'],[])
        _,epoch,_=g.active(root)
        first=epoch/'runs/known/attempt0001/execution.json'
        value=read_json(first)
        value['supervisor_receipt']['supervisor_signature']='corrupted-failed-record'
        write_json(first,value)
        self.assertTrue(evaluate(root)['errors'])

    def test_outer_identity_change_cannot_reuse_signed_record(self):
        value=read_json(self.execution)
        value['run_nonce']='different-nonce'
        write_json(self.execution,value)
        _,epoch,_=g.active(self.root)
        index=read_json(epoch/'attempt_index.json')
        index['experiments']['known'][0]['run_nonce']=value['run_nonce']
        write_json(epoch/'attempt_index.json',index)
        self.assertTrue(any('binding mismatch' in x['detail'] for x in evaluate(self.root)['errors']))

    def test_result_path_and_review_do_not_inflate_assurance(self):
        out=evaluate(self.root)
        self.assertEqual(g._compute_assurance_level(out),'STRUCTURALLY_VALIDATED')
        self.assertEqual(g._assurance_with_review('SEALED_EVALUATION_ATTESTED',True),'STRUCTURALLY_VALIDATED')

    def test_signed_but_impossible_time_envelope_fails(self):
        from engine.supervisor import sign_receipt
        value=read_json(self.execution)
        value['started_at']='2999-01-01T00:00:00+00:00'
        value['supervisor_receipt']['started_at']=value['started_at']
        value['supervisor_receipt']=sign_receipt(value['supervisor_receipt'])
        write_json(self.execution,value)
        self.assertTrue(evaluate(self.root)['errors'])

    def test_real_nested_receipt_verifies_in_portable_bundle(self):
        self.assertEqual(g.handoff(self.root),0)
        bundle=next((self.root/'TAKE_THIS').glob('*.zip'))
        result=verify_bundle(bundle,_pub_key_path())
        self.assertEqual(result['status'],'PASS',result)
        self.assertEqual(result['signatures_verified'],1)


class HardwareScopeCounterexamples(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)
        self.rows='phase,warmup,duration_sec,samples,batch_size,elapsed_sec,energy_joules\n' + 'inference,1,1,1,1,1,1\n' + 'train,0,20,100,100,21,100\n' + ''.join(f'inference,0,1,1,1,{31+10*i},2\n' for i in range(5))
        self.file=self.root/'trials.csv';self.file.write_text(self.rows)
        plan={'hardware':{'experiment_id':'h','min_trials':5,'minimum_sustained_seconds':30,'energy_claim':True}}
        self.audit=Audit(self.root,plan,self.root,{},'fixture')
        self.audit.computed={'h':{'result_path':'result.json'}}
        self.audit.reports={'h':{'hardware_trials':'trials.csv'}}

    def test_inference_energy_does_not_mix_training_denominator(self):
        self.audit.hardware()
        self.assertEqual(self.audit.hardware_results['joules_per_inference_sample'],2)
        self.assertEqual(self.audit.hardware_results['inference_service_samples_per_sec'],1)
        self.assertNotIn('throughput_samples_sec',self.audit.hardware_results)

    def test_aggregate_duration_cannot_be_reported_as_single_request_latency(self):
        self.file.write_text(self.rows.replace('inference,0,1,1,1,','inference,0,1,3,1,'))
        with self.assertRaises(EvidenceError):self.audit.hardware()

    def test_training_time_cannot_extend_inference_measurement_span(self):
        self.file.write_text(self.rows.split('inference,0,')[0]+''.join(
            f'inference,0,1,1,1,{100+.1*i},2\n' for i in range(5)))
        with self.assertRaisesRegex(EvidenceError,'inference clock span'):
            self.audit.hardware()

    def test_unknown_warmup_and_negative_energy_are_rejected(self):
        for text in (self.rows.replace('train,0,','train,2,'),self.rows.replace(',21,100',',21,-100')):
            self.file.write_text(text)
            with self.assertRaises(EvidenceError):self.audit.hardware()
