create or replace function user_trigger() returns trigger as
$$
begin
    return NEW;
end
$$ language plpgsql
    stable
    set search_path = "$user", public;

create trigger create_user_trigger
    before insert
    on "user"
    for each row
execute function user_trigger();