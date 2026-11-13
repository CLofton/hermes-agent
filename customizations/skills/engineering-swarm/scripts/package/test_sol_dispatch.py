"""Offline dispatch tests. No clients, tokens, auth or inference."""
import copy,json,pathlib,unittest
import router
P=json.loads(pathlib.Path(router.__file__).with_name('policy.json').read_text())
class SolDispatch(unittest.TestCase):
 def ctx(self,p=None):return router.PlanContext(p or copy.deepcopy(P),'normal',{})
 def test_coordination_triple(self):
  self.assertEqual(router.coordination_dispatch(self.ctx()),{'model':'gpt-5.6-sol','provider':'openai-codex','reasoning_effort':'high'})
 def test_missing_role_falls_back_to_sol(self):
  p=copy.deepcopy(P);p['tiers']['H'].pop('coordination')
  self.assertEqual(router.coordination_model(self.ctx(p)),'gpt-5.6-sol')
 def test_terra_role_refused(self):
  p=copy.deepcopy(P);p['tiers']['H']['coordination']='gpt-5.6-terra'
  with self.assertRaises(router.PolicyError):router.coordination_dispatch(self.ctx(p))
 def test_wrong_provider_or_reasoning_refused(self):
  for provider,reason in [('openrouter','high'),('openai','high'),('openai-codex','low'),('openai-codex',None)]:
   p=copy.deepcopy(P);s=p['registry']['gpt-5.6-sol'];s['provider']=provider;s['hermes']['reasoning_effort']=reason
   with self.assertRaises(router.PolicyError):router.coordination_dispatch(self.ctx(p))
 def test_no_sol_slug_or_api_key_reference(self):
  s=P['registry']['gpt-5.6-sol'];self.assertNotIn('openrouter_slug',s);self.assertNotIn('key_ref',s);self.assertEqual(s['auth_mode'],'chatgpt')
 def test_kanban_and_worker_argv(self):
  # Existing example produces H-tier Sol work; all card dispatch paths must carry high.
  graph={'nodes':[{'id':'sol','node':'IM','role':'implementer','tier':'H','model':'gpt-5.6-sol'}],'edges':[]}
  cards=router.emit_cards(graph,P,{'task_id':'dispatch-test'},self.ctx())['hermes_cards']
  sol=[c for c in cards if c.get('model')=='gpt-5.6-sol']
  self.assertTrue(sol,'fixture must exercise Sol dispatch')
  for c in sol:
   self.assertEqual(c['dispatch'],router.coordination_dispatch(self.ctx()))
   self.assertIn('--provider openai-codex',c['cli']);self.assertNotIn('--reasoning',c['cli'])
   self.assertEqual(c['worker_argv'][-2:],['--reasoning','high'])
   self.assertEqual(c['reasoning_binding'],'assignee profile agent.reasoning_effort')
 def test_grok_updates_preserved(self):
  self.assertIn('grok-4.6',P['tiers']['F']['candidates']);self.assertIn('grok-4.6',P['tiers']['M']['candidates']);self.assertNotIn('grok-4.20',P['registry'])
if __name__=='__main__':unittest.main()
