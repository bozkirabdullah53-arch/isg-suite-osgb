import {describe,expect,it} from 'vitest';
import {buildOsgbProfessionalSubjects} from './personnel_profile_manager_logic';

describe('OSGB professional digital card scope',()=>{
  it('includes only the three OSGB professional types without assignment requirement',()=>{
    const rows=buildOsgbProfessionalSubjects([
      {id:1,osgb_id:35,full_name:'Uzman',professional_type:'safety_specialist',is_active:true},
      {id:2,osgb_id:35,full_name:'Hekim',professional_type:'workplace_physician',is_active:true},
      {id:3,osgb_id:35,full_name:'DSP',professional_type:'other_health_personnel',is_active:true},
      {id:4,osgb_id:35,full_name:'Operatör',professional_type:'operator',is_active:true},
      {id:5,osgb_id:36,full_name:'Başka OSGB Uzmanı',professional_type:'safety_specialist',is_active:true},
      {id:6,osgb_id:35,full_name:'Pasif Hekim',professional_type:'workplace_physician',is_active:false},
    ],35);
    expect(rows.map((row)=>row.fullName).sort()).toEqual(['DSP','Hekim','Uzman'].sort());
    expect(rows.every((row)=>row.subjectType==='professional')).toBe(true);
    expect(rows.every((row)=>row.companyId===null)).toBe(true);
  });

  it('cannot accept Employee-shaped operator or welder records',()=>{
    const rows=buildOsgbProfessionalSubjects([
      {id:10,company_id:118,full_name:'Ali Yıldırım',job_title:'Operatör',is_active:true},
      {id:11,company_id:118,full_name:'Yusuf Bey',job_title:'Kaynakçı',is_active:true},
    ],35);
    expect(rows).toEqual([]);
  });
});
