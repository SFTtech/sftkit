-- migration: YbcL1B3z3yKj0TrH
-- requires: null

create table "user" (
    id bigint primary key generated always as identity,
    name text not null unique,
    is_registered bool not null default false,
    comment text
);

create table post (
    id bigint primary key generated always as identity,
    title text not null unique,
    author_id bigint not null references "user"(id)
);