create view user_with_post_count as
    select u.*, author_counts.count
    from "user" as u
    join (
        select p.author_id, count(*) as count from post as p group by p.author_id
    ) as author_counts on u.id = author_counts.author_id;