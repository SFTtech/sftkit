create or replace function test_func(
    arg1 bigint,
    arg2 text
) returns boolean as
$$
<<locals>> declare
    tmp_var double precision;
begin
    tmp_var = arg1 > 0 and arg2 != 'bla';
    return tmp_var;
end;
$$ language plpgsql
    set search_path = "$user", public;