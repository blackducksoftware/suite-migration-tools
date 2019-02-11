psql -qA -F '|' -d bds_catalog -o output.csv -c 'select 
cu.approval_status, 
c.name as component_name, 
c.version as component_version, 
cu.kb_license_name, 
a.name as project_name,
a.version as project_version,
u.name as user_name, 
u.first_name, 
u.last_name,
cu.time_submitted,
c.kb_component_id,
c.kb_release_id,
c.id as catalogid,
a.id as projectid 
from componentuse cu join component c on c.id=cu.component 
join application a on a.id =cu.application join enduser u on u.id=cu.owner 
where c.kb_component_id is not null';	