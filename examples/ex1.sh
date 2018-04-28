#PBS -N swembl
#PBS -N swembltoo
#PBS -N
#PBS -k n
#PBS -m n
#PBS -M somebody@somewhere.net
#PBS -j oe
#PBS -o /path/to/output
#PBS -V


function sw()  {
    local s=$1
    shift
    o=$(mktemp temp/XXXX)
    cat > $o <<EOF
bin/SWEMBL -o $o.out -B -z -i $s $@ > $o.log
n=\$(egrep -cv '^#|Region' $o.out)
mw=\$(awk '/^chr/ {n += 1; t += \$5} END {print t / n}' $o.out)
echo "# $(basename $s)|$@|\$n|\$mw" >> $o.log
EOF
echo "bash $o"
}

function sw_ctrl()  {
    local s=$1
    shift
    o=$(mktemp temp/XXXX)
    cat > $o <<EOF
bin/SWEMBL -o $o.out -B -z -i $s -r $ctrl $@ > $o.log
n=\$(egrep -cv '^#|Region' $o.out)
mw=\$(awk '/^chr/ {n += 1; t += \$5} END {print t / n}' $o.out)
echo "# $(basename $s)|$@ -r ctrl|\$n|\$mw" >> $o.log
EOF
echo "bash $o"
}

cd $PBS_O_WORKDIR
# run default settings
ctrl=controls/combined_negative.bed.gz
sample=samples/combined.bed.gz

# vary R
for r in 0 0.0005 0.001 0.0025 0.005 0.0075 0.01 0.02; do
    sw_ctrl $sample -R $r
done
sw $sample -R 0.01

# vary -x
for x in 1 1.1 1.2 1.3 1.4 1.5 2 3; do
    sw_ctrl $sample -R 0.01 -x $x
done

# vary -t
for t in 1 2 3 4 5 10; do
    sw_ctrl $sample -R 0.01 -t $t
done

sw_ctrl $sample -R 0.01 -f 150
sw_ctrl $sample -R 0.01 -f 150 -d50

for d in 70 35 20; do
    sw_ctrl $sample -R 0.01 -d $d
done

# saturation
for f in temp/wt*.bed.gz; do
    sw_ctrl $f -R 0.01 -f 150 
done
