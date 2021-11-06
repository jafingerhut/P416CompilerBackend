/* -*- P4_16 -*- */
#include <core.p4>
#include <v1model.p4>

const bit<16> TYPE_IPV4 = 0x800;

/*************************************************************************
*********************** H E A D E R S  ***********************************
*************************************************************************/

typedef bit<9>  egressSpec_t;
typedef bit<48> macAddr_t;
typedef bit<32> ip4Addr_t;

header ethernet_t {
    macAddr_t dstAddr;
    macAddr_t srcAddr;
    bit<16>   etherType;

}

header my_header {

bit<8>    nsf_22;


}

struct local_metadata_t {
    /* empty */
    bit<4>    nsf_1;
        bit<16>    nsf_2;
        bit<8>    nsf_3;
        bit<8>    nsf_4;
        bit<8>    nsf_5;
        bit<8>    nsf_6;
        bit<8>    nsf_7;
        bit<8>    nsf_8;
        bit<8>    nsf_9;
        bit<8>    nsf_10;
        bit<8>    nsf_11;
}

struct headers {
    ethernet_t   ethernet;
    my_header       my_hdr;
}

/*************************************************************************
*********************** P A R S E R  ***********************************
*************************************************************************/

parser MyParser(packet_in packet,
                out headers hdr,
                inout local_metadata_t meta,
                inout standard_metadata_t standard_metadata) {

    state start {
        transition parse_ethernet;
    }

    state parse_ethernet {
        packet.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            TYPE_IPV4: parse_ipv4;
            default: accept;
        }
    }

    state parse_ipv4 {
        packet.extract(hdr.my_hdr);
        transition accept;
    }

}

/*************************************************************************
************   C H E C K S U M    V E R I F I C A T I O N   *************
*************************************************************************/

control MyVerifyChecksum(inout headers hdr, inout local_metadata_t meta) {
    apply {  }
}


/*************************************************************************
**************  I N G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyIngress(inout headers hdr,
                  inout local_metadata_t meta,
                  inout standard_metadata_t standard_metadata) {
   action set_nsf_3(bit<8> action_param) {
       meta.nsf_3 = action_param;
   }

   table mat_nsf2 {
       key = {
           meta.nsf_2: lpm;
       }
       actions = {
           set_nsf_3;
       }
       size = 1024;

   }
   action set_nsf_6(bit<8> action_param) {
      meta.nsf_6 = action_param;
    }
   table mat_nsf5 {
      key = {
          meta.nsf_5: lpm;
      }
      actions = {
          set_nsf_6;
      }
      size = 1024;

  }



    /*----------------Stateful memory declaration -------------------*------------------*/
    register<bit<16>>(1024) sf_1;
    register<bit<16>>(1024) sf_2;
    register<bit<16>>(1024) sf_3;

    apply {
        if (meta.nsf_1 == 1) {
            if(mat_nsf2.apply().hit){
                sf_1.write((bit<32>)(1), (bit<16>) 0);
                sf_2.write((bit<32>)(1), (bit<16>) 0);
                sf_3.write((bit<32>)(1), (bit<16>) 0);
            }
        }else if (meta.nsf_1 == 2) {
            bit<16> result = 0;
            sf_1.read(result, (bit<32>)2);
            if(meta.nsf_3 >2) {
                meta.nsf_4 = 10;
            }
            if(meta.nsf_4 >2) {
                meta.nsf_5 = 10;
            }
            sf_2.write((bit<32>)(1), (bit<16>) 0);
        }else if (meta.nsf_1 == 3) {
            bit<16> result = 0;
            sf_1.read(result, (bit<32>)2);
            sf_2.read(result, (bit<32>)2);
            if(mat_nsf5.apply().hit){
                sf_3.write((bit<32>)(1), (bit<16>) 0);
            }

        }
    }
}

/*************************************************************************
****************  E G R E S S   P R O C E S S I N G   *******************
*************************************************************************/

control MyEgress(inout headers hdr,
                 inout local_metadata_t meta,
                 inout standard_metadata_t standard_metadata) {
    apply {  }
}

/*************************************************************************
*************   C H E C K S U M    C O M P U T A T I O N   **************
*************************************************************************/

control MyComputeChecksum(inout headers  hdr, inout local_metadata_t meta) {
     apply {

    }
}

/*************************************************************************
***********************  D E P A R S E R  *******************************
*************************************************************************/

control MyDeparser(packet_out packet, in headers hdr) {
    apply {
        packet.emit(hdr.ethernet);
        packet.emit(hdr.my_hdr);
    }
}

/*************************************************************************
***********************  S W I T C H  *******************************
*************************************************************************/

V1Switch(
MyParser(),
MyVerifyChecksum(),
MyIngress(),
MyEgress(),
MyComputeChecksum(),
MyDeparser()
) main;